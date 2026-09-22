# soc2

Review a project, PR, branch, diff, or the current session for SOC 2 Type 2 compliance — Trust Service Criteria coverage across access, change management, availability, confidentiality, and processing integrity.

**Quick start:**
```
/soc2 <PR number, branch, or leave blank for this session's changes>
```

Produces a structured report: scope, a findings table by severity, controls observed, gaps that couldn't be assessed, and a ranked list of next actions. Type 2 means it checks that controls operate *consistently over time* (sampling recent merge history), not just that they exist once.

See [SKILL.md](SKILL.md) for the report format and severity rubric, and `references/controls.md` for the full checklist (includes an AI-inference and GPU-control-plane section for teams serving models).
