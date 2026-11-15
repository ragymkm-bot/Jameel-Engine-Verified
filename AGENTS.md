# Ragy AI Agents — Operating Guide

## Mission

Build a scalable multi-agent system that separates planning, execution, and review while prioritizing free and open-source tooling.

## Core Agent Roles

### Orchestrator

- Receives objectives, decomposes work, assigns bounded tasks, and tracks dependencies.
- Keeps planning separate from execution and quality review.
- Requires explicit human approval before sensitive or irreversible actions.

### Research and Analysis Agent

- Collects, compares, and synthesizes evidence relevant to assigned questions.
- Records assumptions, sources, uncertainty, and recommendations for the Orchestrator.

### Coding and Execution Agent

- Implements approved tasks in small, verifiable increments.
- Runs relevant local checks before handing work to review.
- Does not install software or packages unless explicitly approved.

### Quality and Security Review Agent

- Independently reviews implementations for correctness, maintainability, security, and policy compliance.
- Verifies that tests and validation evidence are sufficient before acceptance.

## Architectural Principles

- Define clear contracts and inputs/outputs between agents.
- Keep agent capabilities narrow, composable, and observable.
- Preserve an audit trail of plans, decisions, changes, reviews, and test results.
- Prefer free and open-source tools and local workflows by default.
- Support Gemini, Grok, OpenRouter, or other model providers only when needed and permitted.
- Keep provider integration behind adapters so models can be changed without redesigning the system.

## Mandatory Safety Rules

- Never use a paid API without explicit human approval.
- Never request, expose, store, print, or transmit API keys or other secrets.
- Never modify or delete files outside this project directory.
- Never perform sensitive actions, including external side effects, deployments, account changes, or irreversible operations, without explicit human approval.
- Test each component before proceeding to the next component or integration step.
- Document material decisions and changes as part of the work.
- Do not install programs, dependencies, or packages unless explicitly approved.

## Delivery Workflow

1. The Orchestrator creates an implementation plan and identifies risks and approval gates.
2. The Research and Analysis Agent provides evidence and constraints when research is needed.
3. The Coding and Execution Agent implements one approved component and validates it locally.
4. The Quality and Security Review Agent reviews the component and its test evidence.
5. The Orchestrator records the result and authorizes the next bounded step.

