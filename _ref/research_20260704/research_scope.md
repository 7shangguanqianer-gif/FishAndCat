# Research Scope

Topic: ABB "智储优控" competition, AI algorithm and intelligent control for 3D warehouse slotting optimization.

Primary objective: collect 2025/2026-focused papers, experiments, open-source projects, benchmark ideas, and implementation references relevant to automated storage/retrieval system slotting, stacker-crane warehouse location assignment, path planning, intelligent control, simulation, and PLC/ST implementation.

Competition constraints:

- 20 x 20 = 400 equal-size storage locations for final visualization.
- Locations whose coordinates are divisible by 3 are pre-occupied, stored continuously from `(0, 0)`.
- Bottom layer load-bearing coefficient is 1.0 and decreases by 0.02 per layer upward.
- Item inputs include id, name, weight, access frequency, and volume.
- Outputs should include assigned storage position, path planning from start to destination, path length, execution time, and total storage time.
- Initial round requires algorithm simulation, verification report, and ABB AC500 PLC Structured Text implementation.
- Final round requires Automation Builder visualization and demo recording.

Research angles:

1. AI and operations-research methods for storage location assignment, warehouse slotting, AS/RS scheduling, and stacker-crane routing.
2. Recent 2025/2026 work on reinforcement learning, graph neural networks, digital twins, simulation optimization, heuristics/metaheuristics, and multi-objective optimization for warehouses.
3. Practical open-source projects and simulation environments that can inform a Python prototype and a PLC-constrained implementation.
4. ABB AC500, CODESYS, PLC Structured Text, and Automation Builder visualization references that affect implementation architecture.
5. Gaps and competition strategy: what is feasible in PLC/ST, what should stay in offline simulation, and how to present algorithm innovation.

Preferred date range: 2025 and 2026. Include older sources only if they are foundational or directly useful.

Deliverable: a Markdown research pack for Claude Code, plus source registries and downloaded originals where legally/publicly accessible.
