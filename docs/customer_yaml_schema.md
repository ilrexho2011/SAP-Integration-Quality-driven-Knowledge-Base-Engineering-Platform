# AI4CPI Customer YAML Configuration Schema

## 1. Purpose

This document defines the standard YAML configuration schema used to describe customer environments in the AI4BIZ platform.

Each customer environment must be represented by a structured YAML configuration file.

The configuration file defines:

- customer identity
- system landscape
- interface environment
- SLA definitions
- automation policies
- monitoring configuration

This configuration is used by the AI4BIZ platform to ensure that AI agents operate in a controlled and customer-aware manner.

## 2. Customer Identity

Each configuration must define the customer identity.

Example structure:

customer:

  customer_id: RCA
  customer_name: RealCore Albania
  environment: production
  region: EU

Fields:

customer_id

Unique identifier of the customer.

customer_name

Human-readable customer name.

environment

Environment classification.

Examples:

production
test
demo

region

Operational region of the customer environment.

Examples:

EU
US
MEA

## 3. System Landscape

Each customer configuration must define the system landscape.

Example structure:

systems:

- system_id: CPI-RCA
    system_type: SAP_CPI
    sap_sid: RO2
    environment: production

- system_id: S4-RCA
    system_type: SAP_S4
    sap_sid: RO2
    environment: production

Fields:

system_id

Unique identifier of the system.

system_type

Technology classification.

Examples:

SAP_PI
SAP_CPI
SAP_S4
SAP_ARIBA
SAP_EWM

sap_sid

Three-character SAP system identifier.

Example:

RO2

environment

Environment classification.

Examples:

production
qa
development

## 4. Interface Monitoring Configuration

The configuration must describe how interfaces are monitored.

Example:

monitoring:

  default_source: SAP_CPI

  alert_types:

    - message_failure
    - authentication_error
    - timeout
    - connection_failure

Fields:

default_source

Primary monitoring source.

Examples:

SAP_PI
SAP_CPI
SAP_S4

alert_types

List of operational event types.

## 5. SLA Definitions

Each customer may define service level expectations.

Example:

sla:

  P1:

    response_time_minutes: 15
    resolution_target_minutes: 120

  P2:

    response_time_minutes: 30
    resolution_target_minutes: 240

  P3:

    response_time_minutes: 120
    resolution_target_minutes: 1440

  P4:

    response_time_minutes: 1440
    resolution_target_minutes: 2880

Fields:

response_time_minutes

Maximum time until first response.

resolution_target_minutes

Target time for issue resolution.

## 6. Automation Policy

Each customer may define automation permissions.

Example:

automation_policy:

  allow_auto_retry: true
  allow_queue_unlock: true
  allow_channel_restart: false
  allow_iflow_restart: false

Fields:

allow_auto_retry

Allows automatic retry actions.

allow_queue_unlock

Allows queue unlock automation.

allow_channel_restart

Allows communication channel restart.

allow_iflow_restart

Allows CPI iFlow restart.

## 7. Governance Rules

Customer YAML configurations must follow governance rules.

Rule 1

Each customer must have a unique customer_id.

Rule 2

Each system_id must be unique within the customer environment.

Rule 3

SAP system identifiers must follow the three-character SAP SID standard.

Rule 4

Automation policies must be explicitly defined.

Rule 5

SLA definitions must exist for P1 to P4 priorities.

Rule 6

Customer YAML configurations must be stored in Git and version controlled.
