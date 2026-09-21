import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL

from tools.system_info import (
    get_system_info
)

from tools.process_monitor import (
    get_top_processes
)

from tools.performance_monitor import (
    monitor_system,
    analyze_trends
)

from tools.diagnostic_engine import (
    diagnose_system
)

from tools.disk_monitor import (
    monitor_disk,
    analyze_disk_trends
)

from tools.anomaly_detector import (
    detect_anomalies
)

from tools.root_cause import (
    calculate_root_causes
)

from tools.investigation_planner import (
    create_investigation_plan
)

from tools.tool_executor import (
    execute_investigation_tool
)

from tools.evidence_fusion import (
    fuse_investigation_evidence
)


logger = logging.getLogger("orion.agent")


class OrionAgent:

    def __init__(self):

        if not GROQ_API_KEY:
            logger.warning(
                "GROQ_API_KEY is not set. LLM calls will fail "
                "until it is configured in the environment/.env file."
            )

        self.client = Groq(
            api_key=GROQ_API_KEY
        )

        self.model = GROQ_MODEL

        # Maximum number of autonomous investigation rounds.
        # This bounds the investigation loop so a misbehaving
        # planner (or a planner that keeps finding "new" work)
        # can never run ORION forever.
        self.max_investigation_rounds = 6

        # Every blocking call into a tool (psutil sampling, disk
        # I/O probes, GPU queries, etc.) is wrapped with this
        # timeout so ORION's own response to the user is never
        # blocked past this many seconds by one hung tool. This
        # is timeout *detection*, not a forced kill of the
        # underlying thread -- see _run_with_timeout()'s
        # docstring for the exact guarantee this provides.
        # Tools intentionally sample for `duration` seconds, so
        # the timeout must comfortably exceed that plus overhead.
        self.tool_timeout_seconds = 45

        # Keep the final LLM request safely below
        # the organization's token-per-minute limit.
        self.max_evidence_characters = 11000
        self.max_prompt_characters = 14000

        # ------------------------------------------------------
        # COMPACT SYSTEM PROMPT
        # ------------------------------------------------------
        #
        # IMPORTANT:
        # Keep this prompt short.
        #
        # The previous version contained a huge duplicated
        # reasoning prompt which pushed the Groq request above
        # the organization's TPM limit.
        #
        # The deterministic Python tools already perform most
        # of the investigation logic.
        #
        # The LLM should interpret the evidence, not repeat
        # the entire diagnostic rulebook.
        # ------------------------------------------------------

        self.system_prompt = """
You are ORION, an evidence-based Field Intelligence system.

Analyze ONLY the supplied measured evidence.

Never invent measurements, causes, services, temperatures,
GPU behavior, network behavior, drivers, malware, or application
behavior.

Core rules:

1. A process is a candidate, not automatically a root cause.
2. Process CPU and system CPU are different measurements.
3. Never add process CPU percentages together.
4. Per-core CPU does not prove process-to-core causation.
5. RAM percentage is not the same as memory pressure.
6. Free disk space is not the same as storage latency.
7. Low GPU activity during a short sample does not prove GPU health.
8. CPU frequency alone does not prove thermal throttling.
9. Missing temperature data remains unknown.
10. svchost.exe does not identify a service without PID-to-service
    evidence.
11. evidence_score means evidence support, NOT probability.

Temporal evidence:

PERSISTENT = strengthens a process hypothesis.
INTERMITTENT = possible contributor.
SHORT_SPIKE = transient/unconfirmed.
LOW_ACTIVITY = weakens the process hypothesis.

Reuse the exact temporal word you are given (PERSISTENT,
INTERMITTENT, SHORT_SPIKE, or LOW_ACTIVITY). Never substitute
a different one, and never invent a compromise label such as
calling LOW_ACTIVITY "short-spike" -- the measured
classification is authoritative, not your own wording of it.

When the investigation's system_conclusion is
NO_PROCESS_CAUSE_CONFIRMED (or similarly indicates nothing was
confirmed), your LIKELY CAUSES section must say plainly that no
cause is confirmed, and list any candidates as unconfirmed
candidates only -- never phrase them as an established or
likely cause. "Candidate" and "confirmed cause" are not
interchangeable.

CONFIDENCE describes how confident ORION is in the stated
conclusion -- which may legitimately be "no cause confirmed" --
not confidence that any single process is guilty. A confident
"no clear cause was found" is a valid, honest answer; do not
convert it into a confident accusation of one candidate.

A "current CPU" reading and a "sampled average/maximum CPU"
value can legitimately differ because they were measured at
different moments -- this is not a contradiction to resolve or
hide. Report both using the labels you are given rather than
picking one or blending them.

Use this reasoning:

MEASURED
→ CANDIDATE
→ INVESTIGATED
→ COMPARE
→ CONFIRM / REJECT / UNCERTAIN

If evidence is insufficient, explicitly say that ORION cannot
confirm the root cause.

Do not turn the highest-scoring candidate into a confirmed cause
unless the evidence actually supports causality.

Use exactly these sections:

OBSERVATION
EVIDENCE
LIKELY CAUSES
CONFIDENCE
NEXT STEP

Maximum 3 likely causes.
Confidence must be HIGH, MODERATE, or LOW.
Keep the answer concise and evidence-based.
"""

    # ==========================================================
    # TIMEOUT-PROTECTED TOOL EXECUTION
    # ==========================================================

    def _run_with_timeout(
        self,
        func,
        *args,
        timeout=None,
        **kwargs
    ):
        """
        Run a blocking tool function on a worker thread and give
        up waiting after a fixed number of seconds.

        This is a best-effort CALLER-SIDE timeout, not a hard
        kill. CPython cannot force-terminate a running thread,
        so if `func` is truly hung (e.g. blocked on a driver call
        that never returns), this method raises TimeoutError and
        control returns to the caller -- but the underlying
        worker thread keeps running in the background, orphaned,
        until `func` itself eventually returns (or the process
        exits). What this DOES guarantee is that the CALLER (the
        code that invoked `_run_with_timeout`) is never blocked
        past `effective_timeout` seconds by a single misbehaving
        tool.

        Note this method deliberately does NOT use
        `with ThreadPoolExecutor(...) as executor:`. That context
        manager's __exit__ calls `executor.shutdown(wait=True)`
        unconditionally, which would block the caller until the
        worker thread finishes -- silently defeating the timeout
        it just raised. Instead, the executor is shut down
        explicitly: `wait=False, cancel_futures=True` on the
        timeout path (so this method returns immediately), and
        `wait=True` on the success/exception path (where the
        worker has already finished, so joining it is instant).

        A true hard kill would require running the tool in a
        separate OS process (e.g. ProcessPoolExecutor) so the
        process itself could be terminated. That was intentionally
        not done here: on Windows, ProcessPoolExecutor uses the
        "spawn" start method, which pays the cost of re-importing
        this module (and psutil, and every tools/* module) on
        every single tool call, and some of the Windows-specific
        tools (e.g. windows_service_inspector, which likely talks
        to WMI/service-manager handles) may not be safe to run in
        a throwaway subprocess. Given the added latency and
        untested cross-process behavior, that trade-off wasn't
        justified for this hardening pass -- if a future version
        needs a true hard kill, that is the mechanism to reach for,
        with each tool module re-verified for subprocess safety
        first.
        """

        effective_timeout = (
            timeout
            if timeout is not None
            else self.tool_timeout_seconds
        )

        executor = ThreadPoolExecutor(max_workers=1)

        future = executor.submit(
            func,
            *args,
            **kwargs
        )

        try:
            result = future.result(
                timeout=effective_timeout
            )

        except FutureTimeoutError:

            logger.warning(
                "%s did not respond within %s seconds; "
                "giving up and continuing. Note: the "
                "underlying thread may still be running "
                "in the background (Python cannot force-"
                "kill a thread).",
                getattr(func, "__name__", "tool"),
                effective_timeout
            )

            # wait=False: do not block this call waiting for the
            # orphaned worker thread. cancel_futures=True: drop
            # any other not-yet-started work from this executor's
            # queue (there is none here, since max_workers=1 and
            # only one task was ever submitted, but it's correct
            # cleanup regardless).
            executor.shutdown(
                wait=False,
                cancel_futures=True
            )

            raise TimeoutError(
                f"{getattr(func, '__name__', 'tool')} "
                f"did not complete within "
                f"{effective_timeout} seconds"
            )

        except Exception:

            # func raised its own exception, which means the
            # worker thread has already finished by the time
            # future.result() re-raised it here -- so waiting for
            # shutdown is effectively instant, not a real block.
            executor.shutdown(
                wait=True,
                cancel_futures=True
            )

            raise

        else:

            # The worker already finished (that's how we have a
            # result), so this join is effectively instant.
            executor.shutdown(
                wait=True,
                cancel_futures=True
            )

            return result

    # ==========================================================
    # COMPACT EVIDENCE
    # ==========================================================

    def build_compact_evidence(
        self,
        system_info,
        process_info,
        trend_analysis,
        diagnostics,
        disk_analysis,
        anomalies,
        root_causes,
        additional_evidence=None,
        investigation_history=None,
        evidence_fusion=None
    ):

        additional_evidence = (
            additional_evidence or []
        )

        investigation_history = (
            investigation_history or []
        )

        evidence_fusion = (
            evidence_fusion or {}
        )

        # ------------------------------------------------------
        # SYSTEM
        # ------------------------------------------------------

        compact_system = {
            "cpu_current": system_info.get(
                "cpu_usage_percent"
            ),
            "cores": system_info.get(
                "cpu_cores"
            ),
            "threads": system_info.get(
                "cpu_threads"
            ),
            "ram_percent": system_info.get(
                "ram_usage_percent"
            ),
            "ram_used_gb": system_info.get(
                "ram_used_gb"
            ),
            "ram_total_gb": system_info.get(
                "ram_total_gb"
            ),
            "disk_free_gb": system_info.get(
                "disk_free_gb"
            )
        }

        # ------------------------------------------------------
        # TOP PROCESSES
        # ------------------------------------------------------

        compact_processes = []

        for process in (
            process_info or []
        )[:6]:

            compact_processes.append({

                "pid":
                    process.get("pid"),

                "name":
                    process.get("name"),

                "cpu":
                    process.get(
                        "cpu_average",
                        process.get(
                            "cpu_percent"
                        )
                    ),

                "cpu_max":
                    process.get(
                        "cpu_maximum"
                    ),

                "memory":
                    process.get(
                        "memory_percent"
                    ),

                "persistence":
                    process.get(
                        "persistence"
                    )
            })

        # ------------------------------------------------------
        # TEMPORAL PROFILES
        # ------------------------------------------------------

        temporal_profiles = []

        for evidence in additional_evidence:

            if evidence.get(
                "tool"
            ) != "process_temporal_profile":

                continue

            for profile in evidence.get(
                "data",
                []
            ):

                cpu = profile.get(
                    "cpu",
                    {}
                )

                memory = profile.get(
                    "memory",
                    {}
                )

                temporal_profiles.append({

                    "pid":
                        profile.get("pid"),

                    "name":
                        profile.get("name"),

                    "cpu_avg":
                        cpu.get("average"),

                    "cpu_max":
                        cpu.get("maximum"),

                    "memory_avg":
                        memory.get("average"),

                    "persistence":
                        profile.get(
                            "persistence"
                        )
                })

        # ------------------------------------------------------
        # SUBSYSTEM RESULTS
        # ------------------------------------------------------

        subsystem_results = []

        for evidence in additional_evidence:

            tool = evidence.get(
                "tool"
            )

            data = evidence.get(
                "data",
                {}
            )

            if tool == (
                "process_temporal_profile"
            ):
                continue

            # --------------------------------------------------
            # GPU
            # --------------------------------------------------

            if tool == "gpu_monitor":

                if isinstance(
                    data,
                    dict
                ):

                    subsystem_results.append({

                        "tool":
                            "gpu",

                        "status":
                            data.get(
                                "status"
                            ),

                        "method":
                            data.get(
                                "method"
                            ),

                        "max_engine":
                            data.get(
                                "maximum_engine_utilization_percent"
                            ),

                        "active_engines":
                            data.get(
                                "average_active_engine_count"
                            )
                    })

            # --------------------------------------------------
            # MEMORY
            # --------------------------------------------------

            elif tool == "memory_pressure":

                if isinstance(
                    data,
                    dict
                ):

                    available = data.get(
                        "available_memory",
                        {}
                    )

                    commit = data.get(
                        "commit",
                        {}
                    )

                    paging = data.get(
                        "paging",
                        {}
                    )

                    subsystem_results.append({

                        "tool":
                            "memory",

                        "status":
                            data.get(
                                "pressure_status"
                            ),

                        "score":
                            data.get(
                                "pressure_score"
                            ),

                        "available_mb":
                            available.get(
                                "minimum_mb"
                            ),

                        "commit_percent":
                            commit.get(
                                "maximum_percent"
                            ),

                        "pages_sec":
                            paging.get(
                                "maximum_pages_per_sec"
                            ),

                        "page_reads":
                            paging.get(
                                "maximum_page_reads_per_sec"
                            ),

                        "page_writes":
                            paging.get(
                                "maximum_page_writes_per_sec"
                            ),

                        "interpretation":
                            data.get(
                                "interpretation"
                            )
                    })

            # --------------------------------------------------
            # STORAGE
            # --------------------------------------------------

            elif tool == "storage_latency":

                if isinstance(
                    data,
                    dict
                ):

                    latency = data.get(
                        "latency",
                        {}
                    )

                    queue = data.get(
                        "queue",
                        {}
                    )

                    subsystem_results.append({

                        "tool":
                            "storage",

                        "status":
                            data.get(
                                "storage_pressure_status"
                            ),

                        "score":
                            data.get(
                                "storage_pressure_score"
                            ),

                        "read_ms":
                            latency.get(
                                "read_average_ms"
                            ),

                        "read_max_ms":
                            latency.get(
                                "read_maximum_ms"
                            ),

                        "write_ms":
                            latency.get(
                                "write_average_ms"
                            ),

                        "write_max_ms":
                            latency.get(
                                "write_maximum_ms"
                            ),

                        "queue_max":
                            queue.get(
                                "maximum"
                            ),

                        "interpretation":
                            data.get(
                                "interpretation"
                            )
                    })

            # --------------------------------------------------
            # PER-CORE CPU
            # --------------------------------------------------

            elif tool == "per_core_cpu":

                if isinstance(
                    data,
                    dict
                ):

                    highest = data.get(
                        "highest_average_core",
                        {}
                    )

                    subsystem_results.append({

                        "tool":
                            "per_core_cpu",

                        "cores":
                            data.get(
                                "logical_cores"
                            ),

                        "highest_core_avg":
                            highest.get(
                                "average"
                            ),

                        "imbalance":
                            data.get(
                                "load_imbalance"
                            ),

                        "distribution":
                            data.get(
                                "load_distribution"
                            )
                    })

            # --------------------------------------------------
            # WINDOWS SERVICES
            # --------------------------------------------------

            elif tool == "windows_services":

                if isinstance(
                    data,
                    dict
                ):

                    subsystem_results.append({

                        "tool":
                            "windows_services",

                        "process_count":
                            data.get(
                                "process_count"
                            ),

                        "services":
                            data.get(
                                "services",
                                []
                            )[:2]
                    })

            # --------------------------------------------------
            # DEEP PROCESS INVESTIGATION
            # --------------------------------------------------

            elif tool == (
                "process_deep_investigation"
            ):

                if isinstance(
                    data,
                    list
                ):

                    deep_items = []

                    for item in data[:3]:

                        deep_items.append({

                            "pid":
                                item.get("pid"),

                            "name":
                                item.get("name"),

                            "status":
                                item.get("status"),

                            "cpu":
                                item.get("cpu_percent"),

                            "memory":
                                item.get("memory_percent"),

                            "threads":
                                item.get("thread_count"),

                            "flags":
                                item.get(
                                    "flags",
                                    []
                                )[:3]
                        })

                    subsystem_results.append({

                        "tool":
                            "deep_process",

                        "results":
                            deep_items
                    })

        # ------------------------------------------------------
        # ANOMALIES
        # ------------------------------------------------------

        compact_anomalies = []

        if isinstance(
            anomalies,
            dict
        ):

            for anomaly in (
                anomalies.get(
                    "anomalies",
                    []
                )[:4]
            ):

                compact_anomalies.append({

                    "type":
                        anomaly.get(
                            "type"
                        ),

                    "severity":
                        anomaly.get(
                            "severity"
                        ),

                    "score":
                        anomaly.get(
                            "score"
                        ),

                    "pid":
                        anomaly.get(
                            "pid"
                        ),

                    "process":
                        anomaly.get(
                            "process"
                        )
                })

        # ------------------------------------------------------
        # ROOT CAUSES
        # ------------------------------------------------------

        compact_root_causes = []

        for cause in (
            root_causes or []
        )[:4]:

            compact_root_causes.append({

                "pid":
                    cause.get("pid"),

                "process":
                    cause.get("process"),

                "score":
                    cause.get(
                        "evidence_score"
                    ),

                "cpu":
                    cause.get(
                        "cpu_percent"
                    ),

                "memory":
                    cause.get(
                        "memory_percent"
                    )
            })

        # ------------------------------------------------------
        # INVESTIGATION HISTORY
        # ------------------------------------------------------

        compact_history = []

        for item in (
            investigation_history or []
        ):

            compact_history.append({

                "round":
                    item.get("round"),

                "tool":
                    item.get("tool"),

                "pids":
                    item.get(
                        "target_pids",
                        []
                    )
            })

        # ------------------------------------------------------
        # EVIDENCE FUSION
        # ------------------------------------------------------

        fusion_summary = {

            "system_pressure":
                evidence_fusion.get(
                    "system_pressure"
                ),

            "system_conclusion":
                evidence_fusion.get(
                    "system_conclusion"
                ),

            "memory":
                (
                    evidence_fusion
                    .get(
                        "memory_evidence",
                        {}
                    )
                    .get(
                        "status"
                    )
                ),

            "storage":
                (
                    evidence_fusion
                    .get(
                        "storage_evidence",
                        {}
                    )
                    .get(
                        "status"
                    )
                ),

            "gpu":
                (
                    evidence_fusion
                    .get(
                        "gpu_evidence",
                        {}
                    )
                    .get(
                        "status"
                    )
                ),

            "candidates": []
        }

        for candidate in (
            evidence_fusion.get(
                "candidates",
                []
            )[:5]
        ):

            fusion_summary[
                "candidates"
            ].append({

                "pid":
                    candidate.get(
                        "pid"
                    ),

                "process":
                    candidate.get(
                        "process"
                    ),

                "score":
                    candidate.get(
                        "evidence_score"
                    ),

                "classification":
                    candidate.get(
                        "classification"
                    ),

                "temporal":
                    candidate.get(
                        "temporal_status"
                    ),

                "deep":
                    candidate.get(
                        "deep_status"
                    )
            })

        # ------------------------------------------------------
        # FINAL OBJECT
        # ------------------------------------------------------

        return {

            "system":
                compact_system,

            "processes":
                compact_processes,

            "trends": {

                "cpu_avg":
                    trend_analysis
                    .get(
                        "cpu",
                        {}
                    )
                    .get(
                        "average"
                    ),

                "cpu_max":
                    trend_analysis
                    .get(
                        "cpu",
                        {}
                    )
                    .get(
                        "maximum"
                    ),

                "ram_avg":
                    trend_analysis
                    .get(
                        "ram",
                        {}
                    )
                    .get(
                        "average"
                    ),

                "ram_max":
                    trend_analysis
                    .get(
                        "ram",
                        {}
                    )
                    .get(
                        "maximum"
                    )
            },

            "diagnostics":
                diagnostics.get(
                    "findings",
                    []
                )[:5]
                if isinstance(
                    diagnostics,
                    dict
                )
                else diagnostics,

            "disk":
                disk_analysis,

            "anomalies":
                compact_anomalies,

            "root_causes":
                compact_root_causes,

            "temporal":
                temporal_profiles,

            "subsystems":
                subsystem_results,

            "history":
                compact_history,

            "fusion":
                fusion_summary
        }

    # ==========================================================
    # SAFE JSON COMPACTION
    # ==========================================================

    def _compact_json(
        self,
        evidence
    ):

        text = json.dumps(
            evidence,
            separators=(
                ",",
                ":"
            ),
            default=str
        )

        # Hard protection against accidentally sending
        # enormous evidence to Groq.
        if len(text) <= self.max_evidence_characters:
            return text

        # Emergency reduced evidence.
        reduced = {

            "system":
                evidence.get(
                    "system",
                    {}
                ),

            "fusion":
                evidence.get(
                    "fusion",
                    {}
                ),

            "temporal":
                evidence.get(
                    "temporal",
                    []
                )[:3],

            "subsystems":
                evidence.get(
                    "subsystems",
                    []
                )[:5],

            "processes":
                evidence.get(
                    "processes",
                    []
                )[:4],

            "root_causes":
                evidence.get(
                    "root_causes",
                    []
                )[:3]
        }

        reduced_text = json.dumps(
            reduced,
            separators=(
                ",",
                ":"
            ),
            default=str
        )

        return reduced_text[
            :self.max_evidence_characters
        ]

    # ==========================================================
    # GROUND-TRUTH REMINDER
    # ==========================================================

    def _build_ground_truth_reminder(
        self,
        evidence
    ):
        """
        Build a short, request-specific reminder derived directly
        from the actual fused_evidence already computed by the
        deterministic engine (evidence_fusion.py). This is
        appended to every prompt sent to the LLM so it cannot
        drift away from the measured facts: it restates the
        exact system_conclusion and the exact temporal_status of
        each top candidate, and tells the LLM to reuse those
        exact words rather than paraphrase or invent a different
        classification.

        This does not change the deterministic engine at all --
        it only makes what the engine already concluded harder
        for the LLM to override or reword.
        """

        fusion = (
            evidence.get(
                "fusion",
                {}
            )
            if isinstance(evidence, dict)
            else {}
        )

        if not fusion:
            return ""

        system_conclusion = fusion.get(
            "system_conclusion"
        )

        candidates = fusion.get(
            "candidates",
            []
        )[:3]

        if not system_conclusion and not candidates:
            return ""

        lines = [
            "",
            "GROUND TRUTH (do not reword or reinterpret these "
            "values -- reuse them exactly as given):",
        ]

        if system_conclusion:

            lines.append(
                f"- system_conclusion = {system_conclusion}"
            )

            if system_conclusion in (
                "NO_PROCESS_CAUSE_CONFIRMED",
            ):
                lines.append(
                    "  This means NO process cause is "
                    "confirmed. Your LIKELY CAUSES section "
                    "must say so explicitly (e.g. \"No "
                    "confirmed cause.\") and list any "
                    "candidates below as UNCONFIRMED "
                    "candidates only, never as an "
                    "established cause."
                )

        for candidate in candidates:

            process = candidate.get("process")
            temporal = candidate.get("temporal")
            classification = candidate.get("classification")

            if not process:
                continue

            lines.append(
                f"- {process}: temporal_status = {temporal}, "
                f"classification = {classification}. "
                f"Describe its temporal behavior using exactly "
                f"the word \"{temporal}\" -- never substitute a "
                f"different temporal word (e.g. do not call "
                f"LOW_ACTIVITY \"short-spike\", or vice versa)."
            )

        lines.append(
            "CONFIDENCE describes how confident ORION is in "
            "the conclusion above (which may legitimately be "
            "\"no cause confirmed\"), not confidence that any "
            "single process is guilty."
        )

        return "\n".join(lines)

    # ==========================================================
    # LLM RESPONSE
    # ==========================================================

    def generate_response(
        self,
        user_question,
        evidence
    ):

        compact_json = self._compact_json(
            evidence
        )

        ground_truth_reminder = (
            self._build_ground_truth_reminder(
                evidence
            )
        )

        prompt = (
            "USER QUESTION:\n"
            + user_question
            + "\n\n"
            "INVESTIGATION EVIDENCE:\n"
            + compact_json
            + ground_truth_reminder
            + "\n\n"
            "Analyze only this evidence. "
            "Do not invent causes. "
            "Distinguish candidates from confirmed causes. "
            "Use exactly the sections OBSERVATION, EVIDENCE, "
            "LIKELY CAUSES, CONFIDENCE, NEXT STEP. "
            "Maximum 3 causes. "
            "Maximum approximately 180 words."
        )

        # ------------------------------------------------------
        # FINAL PROMPT SAFETY
        # ------------------------------------------------------

        if len(prompt) > self.max_prompt_characters:

            prompt = (
                "USER QUESTION:\n"
                + user_question[:1000]
                + "\n\n"
                "KEY ORION EVIDENCE:\n"
                + compact_json[:10500]
                + ground_truth_reminder
                + "\n\n"
                "Give an evidence-based diagnosis. "
                "Do not invent causes. "
                "Use exactly: OBSERVATION, EVIDENCE, "
                "LIKELY CAUSES, CONFIDENCE, NEXT STEP. "
                "Maximum 150 words."
            )

        # ------------------------------------------------------
        # PRIMARY REQUEST
        # ------------------------------------------------------

        try:

            response = (
                self.client
                .chat
                .completions
                .create(

                    model=self.model,

                    messages=[

                        {
                            "role": "system",
                            "content":
                                self.system_prompt
                        },

                        {
                            "role": "user",
                            "content":
                                prompt
                        }

                    ],

                    temperature=0.1,

                    # Raised from 600, then 1200: real answers with
                    # a confirmed strong candidate and multiple
                    # investigation rounds were still getting cut
                    # off before finishing all 5 sections. 2000
                    # gives comfortable headroom above the
                    # prompt's own "~180 words" target.
                    max_completion_tokens=2000
                )
            )

            finish_reason = (
                response
                .choices[0]
                .finish_reason
            )

            content = (
                response
                .choices[0]
                .message
                .content
            )

            if finish_reason == "length":
                logger.warning(
                    "Groq response was truncated by "
                    "max_completion_tokens (finish_reason="
                    "'length'). Consider raising the limit "
                    "further if this repeats."
                )

            if content:

                if finish_reason == "length":
                    content = (
                        content.strip()
                        + "\n\n[Note: this answer was cut off "
                        "before ORION finished writing it.]"
                    )

                return content.strip()

            return (
                "ORION could not generate a final "
                "diagnostic explanation."
            )

        # ------------------------------------------------------
        # LLM / API ERROR HANDLING
        #
        # Any failure here (network outage, invalid/missing API
        # key, rate limiting, oversized request, malformed
        # response, etc.) is caught, logged, and turned into a
        # graceful user-facing message. ORION never lets a Groq
        # API failure crash the whole agent.
        # ------------------------------------------------------

        except Exception as error:

            logger.error(
                "Groq API call failed: %s", error
            )

            error_text = str(
                error
            )

            oversized_or_rate_limited = (
                "413" in error_text
                or "rate_limit_exceeded" in error_text
            )

            if not oversized_or_rate_limited:

                print()
                print(
                    "ORION: The LLM request failed. "
                    "See logs/orion.log for details. "
                    "Returning a fallback response."
                )

                return (
                    "ORION collected diagnostic evidence, but "
                    "could not reach the language model to "
                    "produce a final explanation right now. "
                    "Please check your Groq API key and "
                    "network connection, then try again."
                )

            print()
            print(
                "ORION: Final reasoning request exceeded "
                "the current Groq token limit."
            )

            print(
                "ORION: Retrying with emergency compact evidence..."
            )

            emergency_evidence = {

                "system":
                    evidence.get(
                        "system",
                        {}
                    ),

                "fusion":
                    evidence.get(
                        "fusion",
                        {}
                    ),

                "temporal":
                    evidence.get(
                        "temporal",
                        []
                    )[:2],

                "subsystems":
                    evidence.get(
                        "subsystems",
                        []
                    )[:4],

                "candidates":
                    evidence.get(
                        "root_causes",
                        []
                    )[:3]
            }

            emergency_json = json.dumps(
                emergency_evidence,
                separators=(
                    ",",
                    ":"
                ),
                default=str
            )

            emergency_ground_truth_reminder = (
                self._build_ground_truth_reminder(
                    emergency_evidence
                )
            )

            emergency_prompt = (
                "Question: "
                + user_question[:500]
                + "\n\n"
                "Evidence: "
                + emergency_json[:6000]
                + emergency_ground_truth_reminder
                + "\n\n"
                "Give a concise evidence-based diagnosis. "
                "Do not invent causes. "
                "Use exactly: OBSERVATION, EVIDENCE, "
                "LIKELY CAUSES, CONFIDENCE, NEXT STEP. "
                "Maximum 120 words."
            )

            try:
                retry = (
                    self.client
                    .chat
                    .completions
                    .create(

                        model=self.model,

                        messages=[

                            {
                                "role": "system",
                                "content":
                                    "You are ORION. "
                                    "Use only supplied evidence. "
                                    "Never invent causes. "
                                    "A candidate is not "
                                    "automatically a root cause."
                            },

                            {
                                "role": "user",
                                "content":
                                    emergency_prompt
                            }

                        ],

                        temperature=0.1,

                        max_completion_tokens=400
                    )
                )

                retry_content = (
                    retry
                    .choices[0]
                    .message
                    .content
                )

                if retry_content:
                    return retry_content.strip()

                return (
                    "ORION could not generate a final "
                    "diagnostic explanation."
                )

            except Exception as retry_error:

                logger.error(
                    "Groq emergency retry also failed: %s",
                    retry_error
                )

                return (
                    "ORION collected diagnostic evidence, but "
                    "the language model request failed even "
                    "after retrying with reduced evidence. "
                    "Please check your Groq API key, network "
                    "connection, and account rate limits, then "
                    "try again."
                )

        # ==========================================================
    # INTENT CLASSIFICATION
    # ==========================================================

    def classify_intent(
        self,
        user_input
    ):

        text = (
            user_input
            .lower()
            .strip()
        )

        # ------------------------------------------------------
        # GENERAL KNOWLEDGE / CONVERSATION
        #
        # Questions such as:
        # "Why do AI chips generate heat?"
        # "What is Python?"
        # "Explain quantum computing"
        #
        # must NOT start a laptop investigation.
        # ------------------------------------------------------

        # ------------------------------------------------------
        # STRONG SYSTEM / DEVICE DIAGNOSTIC PHRASES
        # ------------------------------------------------------

        investigation_phrases = [

            "my laptop",

            "my computer",

            "my pc",

            "my system",

            "laptop is slow",

            "computer is slow",

            "pc is slow",

            "system is slow",

            "laptop running slow",

            "computer running slow",

            "pc running slow",

            "laptop is lagging",

            "computer is lagging",

            "pc is lagging",

            "laptop freezes",

            "computer freezes",

            "pc freezes",

            "laptop freezing",

            "computer freezing",

            "pc freezing",

            "check my cpu",

            "check cpu usage",

            "check my ram",

            "check ram usage",

            "check memory usage",

            "check my memory",

            "check my disk",

            "check disk usage",

            "check my system",

            "diagnose my laptop",

            "diagnose my computer",

            "diagnose my pc",

            "diagnose my system",

            "investigate my laptop",

            "investigate my computer",

            "investigate my pc",

            "investigate my system",

            "find what is slowing",

            "what is slowing down my laptop",

            "what is slowing down my computer",

            "what is slowing down my pc",

            "why is my laptop slow",

            "why is my computer slow",

            "why is my pc slow",

            "why is my system slow"
        ]

        # ------------------------------------------------------
        # Check strong phrases first.
        # ------------------------------------------------------

        for phrase in investigation_phrases:

            if phrase in text:

                return "INVESTIGATE"

        # ------------------------------------------------------
        # SYSTEM DIAGNOSTIC WORD COMBINATIONS
        #
        # We require both:
        #
        # 1. A computer-related target
        # 2. A diagnostic/problem word
        #
        # This prevents a normal question containing only
        # "why", "cpu", or "system" from automatically starting
        # a real investigation.
        # ------------------------------------------------------

        device_words = [

            "laptop",

            "computer",

            "pc",

            "windows"
        ]

        problem_words = [

            "slow",

            "slowly",

            "lag",

            "lagging",

            "freeze",

            "freezing",

            "stutter",

            "stuttering",

            "overheat",

            "overheating",

            "hot",

            "unresponsive",

            "crashing",

            "crash"
        ]

        has_device = any(
            word in text
            for word in device_words
        )

        has_problem = any(
            word in text
            for word in problem_words
        )

        if has_device and has_problem:

            return "INVESTIGATE"

        # ------------------------------------------------------
        # Explicit diagnostic requests
        # ------------------------------------------------------

        diagnostic_actions = [

            "diagnose",

            "investigate",

            "analyze my",

            "analyse my",

            "monitor my",

            "check my"
        ]

        system_targets = [

            "cpu",

            "processor",

            "ram",

            "memory",

            "disk",

            "storage",

            "gpu",

            "performance",

            "process",

            "system"
        ]

        has_action = any(
            action in text
            for action in diagnostic_actions
        )

        has_target = any(
            target in text
            for target in system_targets
        )

        if has_action and has_target:

            return "INVESTIGATE"

        # ------------------------------------------------------
        # Everything else is a normal/general question.
        # ------------------------------------------------------

        return "GENERAL"

    # ==========================================================
    # MAIN PROCESS
    # ==========================================================

    def _process_internal(
        self,
        user_input,
        _context=None
    ):
        """
        _context (optional): when a dict is passed in, this
        method fills it in-place with the structured investigation
        data (system_info, fused_evidence, intent) that was
        already computed internally, in addition to returning the
        usual prose string. This lets process_structured() use
        real structured data instead of re-parsing the prose,
        without changing this method's string return type or
        process()'s existing behavior (which never passes
        _context, so it is completely unaffected).
        """

        try:
            text = (
                user_input
                .strip()
            )
        except AttributeError:
            logger.error(
                "process() received a non-string input: %r",
                type(user_input)
            )
            return "ORION could not understand that request."

        if not text:

            return (
                "Please describe the problem "
                "you want ORION to investigate."
            )

        logger.info(
            "User request received (%d chars)",
            len(text)
        )

        intent = self.classify_intent(
            text
        )

        print(
            f"ORION INTENT: {intent}"
        )

        logger.info("Classified intent: %s", intent)

        # ======================================================
        # GENERAL QUESTION
        # ======================================================

        if intent != "INVESTIGATE":

            if _context is not None:
                _context["intent"] = intent
                _context["system_info"] = {}
                _context["fused_evidence"] = {}

            return self.generate_response(

                text,

                {
                    "message":
                        "No system investigation "
                        "was requested."
                }
            )

        # ======================================================
        # INITIAL INVESTIGATION
        #
        # Every step below is independently wrapped: if one
        # data source fails or hangs, ORION logs it, falls back
        # to a safe empty value, and keeps going rather than
        # crashing the whole request. The LLM is told evidence
        # is incomplete via the empty/default values it receives.
        # ======================================================

        print(
            "[1/9] system information"
        )

        try:
            system_info = self._run_with_timeout(
                get_system_info
            )
        except Exception as error:
            logger.error(
                "system_info collection failed: %s", error
            )
            system_info = {}

        print(
            "[2/9] performance monitoring"
        )

        try:
            snapshots = self._run_with_timeout(
                monitor_system,
                duration=6,
                interval=2
            )
            trend_analysis = analyze_trends(snapshots)
        except Exception as error:
            logger.error(
                "performance monitoring failed: %s", error
            )
            snapshots = []
            trend_analysis = {}

        print(
            "[3/9] process monitoring over time"
        )

        try:
            process_info = self._run_with_timeout(
                get_top_processes,
                limit=10,
                duration=6,
                interval=2
            )
        except Exception as error:
            logger.error(
                "process monitoring failed: %s", error
            )
            process_info = []

        print(
            "[4/9] deterministic diagnostics"
        )

        try:
            diagnostics = diagnose_system(
                system_info,
                process_info,
                trend_analysis
            )
        except Exception as error:
            logger.error(
                "diagnostic_engine failed: %s", error
            )
            diagnostics = {}

        print(
            "[5/9] disk monitoring"
        )

        try:
            disk_snapshots = self._run_with_timeout(
                monitor_disk,
                duration=6,
                interval=2
            )
            disk_analysis = analyze_disk_trends(disk_snapshots)
        except Exception as error:
            logger.error(
                "disk monitoring failed: %s", error
            )
            disk_snapshots = []
            disk_analysis = {}

        print(
            "[6/9] anomaly detection"
        )

        try:
            anomalies = detect_anomalies(
                system_info,
                process_info,
                trend_analysis,
                disk_analysis
            )
        except Exception as error:
            logger.error(
                "anomaly_detector failed: %s", error
            )
            anomalies = {}

        print(
            "[7/9] root-cause ranking"
        )

        try:
            root_causes = calculate_root_causes(
                process_info,
                anomalies,
                trend_analysis
            )
        except Exception as error:
            logger.error(
                "root_cause ranking failed: %s", error
            )
            root_causes = []

        # ======================================================
        # INVESTIGATION STATE
        # ======================================================

        completed_tools = []

        investigation_history = []

        additional_evidence = []

        # ======================================================
        # ITERATIVE INVESTIGATION
        # ======================================================

        for round_number in range(

            1,

            self.max_investigation_rounds + 1
        ):

            print()

            print(
                "========== INVESTIGATION ROUND "
                + str(round_number)
                + " =========="
            )

            logger.info(
                "Investigation round %d/%d starting",
                round_number,
                self.max_investigation_rounds
            )

            print(
                "ORION planner is deciding what "
                "to investigate next..."
            )

            try:
                investigation_plan = (
                    create_investigation_plan(

                        system_info=
                            system_info,

                        process_info=
                            process_info,

                        anomalies=
                            anomalies,

                        root_causes=
                            root_causes,

                        completed_tools=
                            completed_tools,

                        additional_evidence=
                            additional_evidence
                    )
                )
            except Exception as error:
                logger.error(
                    "investigation_planner failed on round "
                    "%d: %s",
                    round_number,
                    error
                )
                print(
                    "ORION planner failed for this round; "
                    "stopping the investigation loop safely."
                )
                break

            if not isinstance(investigation_plan, dict):
                logger.error(
                    "investigation_planner returned a "
                    "malformed plan (%s); stopping loop.",
                    type(investigation_plan)
                )
                break

            next_tool = (
                investigation_plan.get(
                    "next_tool"
                )
            )

            if not next_tool:

                print(
                    "ORION has no new investigation "
                    "to perform."
                )

                break

            target_pids = (
                investigation_plan.get(
                    "target_pids",
                    []
                )
            )

            # --------------------------------------------------
            # DUPLICATE PROCESS PROTECTION
            # --------------------------------------------------

            if next_tool == (
                "process_temporal_profile"
            ):

                already_profiled = set()

                for evidence in (
                    additional_evidence
                ):

                    if evidence.get(
                        "tool"
                    ) != "process_temporal_profile":

                        continue

                    for profile in (
                        evidence.get(
                            "data",
                            []
                        )
                    ):

                        pid = profile.get(
                            "pid"
                        )

                        if pid is not None:

                            already_profiled.add(
                                pid
                            )

                target_pids = [

                    pid

                    for pid in target_pids

                    if pid
                    not in already_profiled
                ]

                if not target_pids:

                    if next_tool not in (
                        completed_tools
                    ):

                        completed_tools.append(
                            next_tool
                        )

                    continue

            # --------------------------------------------------
            # DISPLAY PLAN
            # --------------------------------------------------

            print(
                "ORION selected next tool: "
                + str(
                    next_tool
                )
            )

            if target_pids:

                print(
                    "Target PIDs: "
                    + str(
                        target_pids
                    )
                )

            print(
                "Reason: "
                + str(
                    investigation_plan.get(
                        "reason",
                        "No reason supplied."
                    )
                )
            )

            print(
                "Executing investigation tool: "
                + str(
                    next_tool
                )
            )

            logger.info(
                "Round %d: selected tool=%s target_pids=%s",
                round_number,
                next_tool,
                target_pids
            )

            # --------------------------------------------------
            # EXECUTE (timeout + error protected)
            #
            # Investigation tools are only ever invoked by name
            # through execute_investigation_tool's internal
            # allowlist dispatch -- ORION never lets the LLM (or
            # anything else) run arbitrary code. A failure or
            # hang here is recorded as evidence and the loop
            # continues instead of crashing the whole request.
            # --------------------------------------------------

            try:
                result = self._run_with_timeout(
                    execute_investigation_tool,

                    next_tool,

                    duration=6,

                    interval=2,

                    target_pids=target_pids
                )

                if not isinstance(result, dict):
                    raise ValueError(
                        "tool returned a non-dict result: "
                        f"{type(result)}"
                    )

                logger.info(
                    "Round %d: tool %s finished with status %s",
                    round_number,
                    next_tool,
                    result.get("status")
                )

            except Exception as error:

                logger.error(
                    "Round %d: tool %s failed: %s",
                    round_number,
                    next_tool,
                    error
                )

                print(
                    "Investigation tool "
                    + str(next_tool)
                    + " failed. Continuing with the next "
                    "step. (See logs/orion.log for details.)"
                )

                result = {
                    "tool": next_tool,
                    "status": "FAILED",
                    # Only the exception's class name is kept
                    # here (e.g. "PermissionError", "TimeoutError").
                    # This evidence dict is later fed into the
                    # planner, evidence fusion, and the LLM's
                    # prompt -- and the LLM's answer is shown
                    # directly to the user -- so the full
                    # exception message (which can contain file
                    # paths, PIDs, or other internal detail) is
                    # deliberately NOT included here. It is
                    # already captured in full via logger.error()
                    # above, in logs/orion.log.
                    "error": type(error).__name__,
                    "data": {}
                }

            # --------------------------------------------------
            # REMEMBER TOOL
            #
            # A tool is marked completed whether it succeeded or
            # failed, so a persistently broken/hanging tool can
            # never be retried in a tight loop -- the planner
            # will move on to something else next round.
            # --------------------------------------------------

            if next_tool not in (
                completed_tools
            ):

                completed_tools.append(
                    next_tool
                )

            # --------------------------------------------------
            # HISTORY
            # --------------------------------------------------

            investigation_history.append({

                "round":
                    round_number,

                "tool":
                    next_tool,

                "target_pids":
                    target_pids,

                "status":
                    result.get(
                        "status"
                    )
            })

            # --------------------------------------------------
            # EVIDENCE
            # --------------------------------------------------

            additional_evidence.append(
                result
            )

            print(
                "Investigation result:"
            )

            print(
                result
            )

            print(
                "Round "
                + str(
                    round_number
                )
                + " complete."
            )

        # ======================================================
        # EVIDENCE FUSION
        # ======================================================

        print()

        print(
            "=========================================="
        )

        print(
            "ORION is fusing investigation evidence..."
        )

        print(
            "=========================================="
        )

        try:
            fused_evidence = (
                fuse_investigation_evidence(

                    system_info=
                        system_info,

                    process_info=
                        process_info,

                    anomalies=
                        anomalies,

                    root_causes=
                        root_causes,

                    trend_analysis=
                        trend_analysis,

                    additional_evidence=
                        additional_evidence
                )
            )
        except Exception as error:
            logger.error(
                "evidence_fusion failed: %s", error
            )
            print(
                "ORION could not fuse evidence; falling back "
                "to raw root-cause ranking for the final answer."
            )
            fused_evidence = {}

        if _context is not None:
            _context["intent"] = "INVESTIGATE"
            _context["system_info"] = system_info
            _context["fused_evidence"] = fused_evidence

        # ======================================================
        # DISPLAY FUSION
        # ======================================================

        print()

        print(
            "========== EVIDENCE FUSION =========="
        )

        print(
            "System pressure: "
            + str(
                fused_evidence.get(
                    "system_pressure"
                )
            )
        )

        print(
            "System conclusion: "
            + str(
                fused_evidence.get(
                    "system_conclusion"
                )
            )
        )

        for candidate in (
            fused_evidence.get(
                "candidates",
                []
            )[:5]
        ):

            print(

                "- "

                + str(
                    candidate.get(
                        "process"
                    )
                )

                + " (PID "

                + str(
                    candidate.get(
                        "pid"
                    )
                )

                + "): "

                + str(
                    candidate.get(
                        "classification",
                        candidate.get(
                            "status",
                            "UNKNOWN"
                        )
                    )
                )

                + " | score="

                + str(
                    candidate.get(
                        "evidence_score",
                        0
                    )
                )

                + " | temporal="

                + str(
                    candidate.get(
                        "temporal_status",
                        "NO_DATA"
                    )
                )

                + " | deep="

                + str(
                    candidate.get(
                        "deep_status",
                        "NO_DATA"
                    )
                )
            )

        # ------------------------------------------------------
        # MEMORY
        # ------------------------------------------------------

        memory_evidence = (
            fused_evidence.get(
                "memory_evidence",
                {}
            )
        )

        print(
            "- MEMORY: "
            + str(
                memory_evidence.get(
                    "status",
                    "NOT_TESTED"
                )
            )
        )

        # ------------------------------------------------------
        # STORAGE
        # ------------------------------------------------------

        storage_evidence = (
            fused_evidence.get(
                "storage_evidence",
                {}
            )
        )

        print(
            "- STORAGE: "
            + str(
                storage_evidence.get(
                    "status",
                    "NOT_TESTED"
                )
            )
        )

        # ------------------------------------------------------
        # GPU
        # ------------------------------------------------------

        gpu_evidence = (
            fused_evidence.get(
                "gpu_evidence",
                {}
            )
        )

        print(
            "- GPU: "
            + str(
                gpu_evidence.get(
                    "status",
                    "NOT_TESTED"
                )
            )
        )

        # ======================================================
        # FINAL COMPACT EVIDENCE
        # ======================================================

        final_evidence = (
            self.build_compact_evidence(

                system_info=
                    system_info,

                process_info=
                    process_info,

                trend_analysis=
                    trend_analysis,

                diagnostics=
                    diagnostics,

                disk_analysis=
                    disk_analysis,

                anomalies=
                    anomalies,

                root_causes=
                    root_causes,

                additional_evidence=
                    additional_evidence,

                investigation_history=
                    investigation_history,

                evidence_fusion=
                    fused_evidence
            )
        )

        # ======================================================
        # FINAL REASONING
        # ======================================================

        print()

        print(
            "=========================================="
        )

        print(
            "ORION is reasoning over all "
            "investigation evidence..."
        )

        print(
            "=========================================="
        )

        response = (
            self.generate_response(

                text,

                final_evidence
            )
        )
        return response


    # ==========================================================
    # PUBLIC TEXT INTERFACE
    # ==========================================================

    def process(
        self,
        user_input
    ):
        """
        Backward-compatible text interface.

        Existing callers that expect a plain ORION response
        continue to receive a string.
        """

        return self._process_internal(
            user_input
        )


    # ==========================================================
    # PUBLIC STRUCTURED INTERFACE
    # ==========================================================

    def process_structured(
        self,
        user_input
    ):
        """
        Structured interface for the API and dashboard.

        The investigation engine remains unchanged.
        This method converts the final ORION response into
        an API-friendly structure.
        """

        try:
            text = (
                user_input.strip()
            )
        except AttributeError:

            return {
                "success": False,
                "intent": "UNKNOWN",
                "status": "failed",
                "response": (
                    "ORION could not understand "
                    "that request."
                ),
                "diagnosis": {
                    "observation": "",
                    "evidence": "",
                    "likely_causes": "",
                    "confidence": "UNKNOWN",
                    "next_step": ""
                }
            }

        if not text:

            return {
                "success": False,
                "intent": "UNKNOWN",
                "status": "failed",
                "response": (
                    "Please describe the problem "
                    "you want ORION to investigate."
                ),
                "diagnosis": {
                    "observation": "",
                    "evidence": "",
                    "likely_causes": "",
                    "confidence": "UNKNOWN",
                    "next_step": ""
                }
            }

        intent = self.classify_intent(
            text
        )

        context = {}

        response = self._process_internal(
            text,
            _context=context
        )

        # ------------------------------------------------------
        # Extract the structured diagnosis from ORION's
        # controlled five-section response.
        #
        # This keeps the investigation engine independent
        # from FastAPI.
        # ------------------------------------------------------

        from api.response_formatter import (
            format_orion_response
        )

        return format_orion_response(
            user_question=text,
            intent=context.get("intent", intent),
            response_text=response,
            structured_evidence=context
        )


# ==============================================================
# GLOBAL ORION INSTANCE
# ==============================================================
orion = OrionAgent()