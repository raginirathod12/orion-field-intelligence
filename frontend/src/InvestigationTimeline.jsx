import React from "react";

const steps = [
  {
    key: "observe",
    label: "OBSERVE",
    description: "Collecting live system telemetry",
  },
  {
    key: "analyze",
    label: "ANALYZE",
    description: "Analyzing CPU, memory, disk and processes",
  },
  {
    key: "investigate",
    label: "INVESTIGATE",
    description: "Testing candidate causes",
  },
  {
    key: "fuse",
    label: "FUSE EVIDENCE",
    description: "Combining independent evidence",
  },
  {
    key: "diagnose",
    label: "DIAGNOSE",
    description: "Producing an evidence-based conclusion",
  },
];


export default function InvestigationTimeline({
  activeStep = "diagnose",
}) {

  const activeIndex = steps.findIndex(
    (step) => step.key === activeStep
  );

  return (
    <div className="investigation-timeline">

      <div className="timeline-header">
        <div>
          <div className="timeline-title">
            ORION Investigation
          </div>

          <div className="timeline-subtitle">
            Observe → Investigate → Reason → Verify
          </div>
        </div>

        <div className="timeline-status">
          {activeIndex >= steps.length - 1
            ? "COMPLETE"
            : "IN PROGRESS"}
        </div>
      </div>


      <div className="timeline-steps">

        {steps.map((step, index) => {

          const completed = index < activeIndex;
          const active = index === activeIndex;

          return (
            <React.Fragment key={step.key}>

              <div
                className={[
                  "timeline-step",
                  completed ? "completed" : "",
                  active ? "active" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >

                <div className="timeline-node">
                  {completed ? "✓" : index + 1}
                </div>

                <div className="timeline-content">

                  <div className="timeline-step-label">
                    {step.label}
                  </div>

                  <div className="timeline-step-description">
                    {step.description}
                  </div>

                </div>

              </div>

              {index < steps.length - 1 && (
                <div
                  className={[
                    "timeline-connector",
                    index < activeIndex ? "completed" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                />
              )}

            </React.Fragment>
          );
        })}

      </div>

    </div>
  );
}