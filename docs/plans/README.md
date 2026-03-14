# Comic Translate — Design Plans

This directory contains design documents, technical specifications, and implementation plans for the comic translation system.

## Directory Structure

```
docs/plans/
├── README.md                           # This file
├── architecture/                       # System architecture & design patterns
│   ├── pipeline-v2-overview.md        # PIPELINE_V2 high-level architecture
│   └── qa-system-design.md            # QA module design (interfaces + patterns)
├── features/                           # Feature-specific designs
│   ├── script-export-qa.md            # Script export + QA patch system
│   ├── multi-version-fingerprinting.md # Multi-version/multi-source data model
│   ├── nsfw-routing.md                # NSFW semantic routing + local-only handling
│   └── relay-network.md               # h@H-inspired relay network (optional)
├── implementation/                     # Implementation plans (step-by-step)
│   ├── 2026-03-14-qa-phase1.md        # Phase 1: JSON backend + OpenAI provider
│   └── ...
├── legacy/                             # Historical plans (reference only)
│   ├── manga_translation_system_plan.md
│   ├── 2026-02-20-manga-translation-system.md
│   ├── 2026-02-20-sfx-sound-effects-positioning.md
│   └── 2026-02-23-zip-extraction-performance-design.md
└── reviews/                            # Code reviews & retrospectives
    └── CODE_REVIEW.md
```

## Document Types

### Architecture Documents
High-level system design, design patterns, and architectural decisions. These are **stable** and change infrequently.

- Focus: interfaces, abstractions, component relationships
- Audience: architects, senior developers
- Lifecycle: long-term reference

### Feature Designs
Detailed specifications for individual features or subsystems. These are **evolving** and may be updated as requirements change.

- Focus: data models, workflows, API contracts
- Audience: feature developers, QA
- Lifecycle: active during feature development, archived after completion

### Implementation Plans
Step-by-step execution plans with concrete tasks, file paths, and code snippets. These are **tactical** and short-lived.

- Focus: what to build, in what order, with what code
- Audience: implementers (human or AI agents)
- Lifecycle: active during sprint, archived after merge

### Legacy Documents
Historical plans kept for reference. Not actively maintained.

### Reviews
Code review notes, retrospectives, and lessons learned.

---

## Active Plans (2026-03-14)

### In Progress
- **Script Export + QA System** (`features/script-export-qa.md`)
  - Status: Design complete, Phase 1 implementation pending
  - Owner: mythic3014
  - Next: Implement JSON backend + OpenAI provider

### Planned
- **Multi-Version Fingerprinting** (`features/multi-version-fingerprinting.md`)
  - Status: Spec draft in PIPELINE_V2
  - Depends on: Script export system

- **NSFW Routing** (`features/nsfw-routing.md`)
  - Status: Spec draft in PIPELINE_V2
  - Depends on: Semantic routing module

### On Hold
- **Relay Network** (`features/relay-network.md`)
  - Status: Design only, no implementation timeline
  - Reason: Optional feature, low priority

---

## How to Use This Directory

### When Starting a New Feature
1. Check if an architecture doc exists for the subsystem
2. Create a feature design doc in `features/`
3. Break down into implementation plan in `implementation/`
4. Reference existing designs to maintain consistency

### When Updating a Design
- Architecture docs: require review + approval
- Feature designs: update freely during active development
- Implementation plans: create new dated versions, don't edit old ones

### When a Feature is Complete
- Move implementation plan to `legacy/` or delete
- Keep feature design doc if it's a stable API/interface
- Update architecture doc if system structure changed

---

## Design Principles

All plans in this directory follow these principles:

1. **Interface-First**: Define abstractions before implementations
2. **Open/Closed**: Designs should be extensible without modification
3. **YAGNI**: Only design what's needed now, not hypothetical futures
4. **Incremental**: Break large designs into phases
5. **Testable**: Every design should specify how to verify correctness

---

## Related Documentation

- `/CLAUDE.md` — Project overview and development commands
- `/docs/architecture/` — (future) Detailed architecture diagrams
- `/docs/api/` — (future) API reference documentation
