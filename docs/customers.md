# Customer Architecture Model

AI4CPI is designed as a multi-customer platform.

Each customer has a configuration stored in:

control-plane/customers/<CUSTOMER_ID>.yaml

Example:

RCA.yaml

## Customer Attributes

customer_id  
display_name  
systems  
interfaces  
priority_scheme  
monitoring_rules  
kedb_location

## Example Systems

- SAP PI/PO
- SAP CPI
- SAP S4
- External Monitoring Tools

## Knowledge Sources

Each customer has dedicated knowledge sources:

- KEDB
- Integration documentation
- Runbooks
- Monitoring logs
