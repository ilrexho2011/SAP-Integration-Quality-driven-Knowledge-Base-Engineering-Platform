# AI4CPI Automation Action Library

## 1. Purpose

This document defines the automation action library of the AI4CPI platform.

The action library specifies which operational actions the AI agent may recommend or execute.

The purpose of this document is to ensure that automation is:

- safe
- controlled
- auditable
- customer-aware
- aligned with operational governance

No automated action may be executed without being defined in this library.

## 2. Action Model

Each automation action must be defined as a structured action object.

Each action object describes:

- what the action does
- in which system it is allowed
- whether it is safe
- whether manual approval is required
- how the action is logged

Mandatory fields:

- action_id
- action_name
- system_type
- action_category
- safety_level
- execution_mode
- allowed_in_prod
- requires_approval
- rollback_possible
- logging_required

## 3. Safety Levels

Each action must be classified by safety level.

### Level 1 – Safe Automation

Actions with low operational risk.

Examples:

- message retry
- queue unlock
- re-trigger failed message

These actions may be executed automatically if customer policy allows it.

### Level 2 – Controlled Automation

Actions with medium operational impact.

Examples:

- communication channel restart
- CPI iFlow restart
- service restart

These actions may require additional checks or policy approval.

### Level 3 – Manual Approval Required

Actions with high operational or business impact.

Examples:

- configuration changes
- endpoint changes
- credential updates
- transport-related actions

These actions must never be executed automatically without manual approval.

## 4. Execution Modes

The AI4CPI platform supports different execution modes.

Allowed execution modes:

- recommend_only
- assisted_execution
- automatic_execution

recommend_only

The AI agent proposes an action but does not execute it.

assisted_execution

The AI agent prepares the action and a human confirms execution.

automatic_execution

The AI agent executes the action automatically according to policy rules.

## 5. Example Actions

Examples of supported automation actions.

### PI Channel Restart

action_id: ACT_PI_CHANNEL_RESTART
action_name: Restart PI Communication Channel
system_type: SAP_PI
action_category: restart
safety_level: Level 2
execution_mode: assisted_execution
allowed_in_prod: true
requires_approval: true
rollback_possible: false
logging_required: true

### CPI iFlow Restart

action_id: ACT_CPI_IFLOW_RESTART
action_name: Restart CPI iFlow
system_type: SAP_CPI
action_category: restart
safety_level: Level 2
execution_mode: assisted_execution
allowed_in_prod: true
requires_approval: true
rollback_possible: false
logging_required: true

### IDoc Reprocessing

action_id: ACT_S4_IDOC_REPROCESS
action_name: Reprocess Failed IDoc
system_type: SAP_S4
action_category: retry
safety_level: Level 1
execution_mode: automatic_execution
allowed_in_prod: true
requires_approval: false
rollback_possible: false
logging_required: true

### Queue Unlock

action_id: ACT_QUEUE_UNLOCK
action_name: Unlock Processing Queue
system_type: SAP_S4
action_category: queue_action
safety_level: Level 1
execution_mode: automatic_execution
allowed_in_prod: true
requires_approval: false
rollback_possible: false
logging_required: true

## 6. Automation Governance Rules

All automation actions must follow strict governance rules.

### Rule 1 – Explicit Definition Required

No action may be executed unless it is explicitly defined in this action library.

### Rule 2 – Customer Policy Must Allow Execution

Even if an action exists in the library, execution is only allowed if the customer configuration permits it.

### Rule 3 – Production Restrictions Apply

Not all actions are allowed in productive environments.

Production execution must always check:

- allowed_in_prod
- execution_mode
- customer policy
- system state

### Rule 4 – Logging Is Mandatory

Every executed action must be logged.

The log must include:

- customer_id
- system_id
- action_id
- action_timestamp
- execution_result
- related_incident

### Rule 5 – Approval Workflow

Actions requiring approval must not bypass the approval process.

### Rule 6 – Rollback Awareness

If rollback is not possible, the action must be treated with higher caution.

### Rule 7 – Continuous Review

The action library must be reviewed regularly by engineering and platform governance teams.
