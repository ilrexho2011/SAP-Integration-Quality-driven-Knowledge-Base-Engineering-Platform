# Scenario Lab analysis summary - 20260601_000335

## Source Map
- Primary evidence folder: `C:\Users\RexhoIlirjan\quality-driven-knowledge-engineering-platform-v2.0.9\resources\cpi\input\odata\iflows`
- Secondary evidence folder: `C:\Users\RexhoIlirjan\quality-driven-knowledge-engineering-platform-v2.0.9\resources\cpi\input\analysis\iflows-bpmn`
- iFlows analyzed: 241
- Adapter hints found: AI, AMQP, FTP, GooglePubSub, HCIOData, HTTP, HTTPS, JDBC, Jira, Mail, OpenConnectors, PollingSFTP, ProcessDirect, SFTP, SOAP, ServiceNow

## Source-backed facts
- ZIP names, package names, iFlow names, SHA-256 checksums, and available BPMN file matches are source-backed.
- Scripts, mappings, dependencies, endpoints, and adapter hints are source-backed when present in ZIP/BPMN/CPIView evidence.
- CPIView rich inventory records include runtime status, channel properties, configurations, scripts, mappings, timers, and resources when available.

## Assumptions
- Negative examples are safe functional DEV/TEST inputs, not destructive or security attack payloads.
- Runtime evidence must be collected after execution from Live MPL or Archived MPL.

## Risks and Open Points
- Some BPMN exports may omit endpoint or adapter direction metadata; validate in deployed artifact view before execution.
- Do not execute examples in production.

## Top iFlows
- `IR07_IF05_Calculator_Simulation_Mapping` | package `07 - Message Routing - Routers` | runtime `STARTED` | risks: 2
- `IR07_IF01_Router_First_Example` | package `07 - Message Routing - Routers` | runtime `STARTED` | risks: 1
- `IR07_IF02_Router_You_always_have_a_choice` | package `07 - Message Routing - Routers` | runtime `STARTED` | risks: 1
- `IR07_IF03_Router_End_or_continue_if_no_data` | package `07 - Message Routing - Routers` | runtime `STARTED` | risks: 1
- `IR07_IF06_Router_Configuration` | package `07 - Message Routing - Routers` | runtime `STARTED` | risks: 1
- `IR07_IF04_Calculator_Simulation_Groovy` | package `07 - Message Routing - Routers` | runtime `STARTED` | risks: 2
- `IR09_IF03_Multicast_manually_with_Local_Integration_Processes` | package `09 - Message Routing - Multicasting` | risks: 2
- `IR09_IF02_Multicast_manually` | package `09 - Message Routing - Multicasting` | risks: 2
- `IR09_IF05_Header_and Property_Access_BeforeDuringAndAfter_Multicast` | package `09 - Message Routing - Multicasting` | risks: 2
- `IR09_IF01_Multicast_with_multiple_routings` | package `09 - Message Routing - Multicasting` | risks: 2
- `IR09_IF04_Multicast_in_multiple_routing_and_combined_gatherof_all_messages` | package `09 - Message Routing - Multicasting` | risks: 2
- `IR06_IF01_SFTP_Passthrough_People_Source_to_Target` | package `06 - Practice with SFTP Adapter` | runtime `STARTED` | risks: 1
- `IR06_IF02_SFTP_Passthrough_Source_to_Target` | package `06 - Practice with SFTP Adapter` | runtime `STARTED` | risks: 1
- `IR06_IF03_SFTP_Passthrough_Sub_Source_to_Target` | package `06 - Practice with SFTP Adapter` | runtime `STARTED` | risks: 1
- `IR06_IF04_SFTP_Poll_Enrich_Multiple_File_and_Delete` | package `06 - Practice with SFTP Adapter` | runtime `STARTED` | risks: 1
- `IR06_IF05_SFTP_Poll_Enrich_Single_File` | package `06 - Practice with SFTP Adapter` | runtime `STARTED` | risks: 1
- `IR06_IF06_Sending_File_Sftp2Ftp` | package `06 - Practice with SFTP Adapter` | risks: 2
- `IR08_IF06_Split_by_Token` | package `08 - Message Routing - Splitters` | risks: 2
- `IR08_IF07_Split_XML_with_namespaces` | package `08 - Message Routing - Splitters` | risks: 3
- `IR08_IF05_Split_by_Line_Break` | package `08 - Message Routing - Splitters` | risks: 2
- `IR08_IF02_Iterating_Splitter` | package `08 - Message Routing - Splitters` | runtime `STARTED` | risks: 1
- `IR08_IF03_Nested_General_Splitter` | package `08 - Message Routing - Splitters` | runtime `STARTED` | risks: 1
- `IR08_IF01_General_Splitter` | package `08 - Message Routing - Splitters` | runtime `STARTED` | risks: 1
- `IR08_IF04_Nested_Iterating_Splitter` | package `08 - Message Routing - Splitters` | runtime `STARTED` | risks: 1
- `IR10_IF11_Data_Conversion_Encoding_Decoding` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF03_Convert_XML_to_CSV_Occurrence` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF04_Convert_CSV_to_XML_Columns` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF01_Convert_XML_to_JSON_number_boolean_null_empty ` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF07_Base64_Encoding_Decoding` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF04_Convert_CSV_to_XML` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF02_Convert_JSON_with_array_to_XML` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF03_Convert_XML_to_CSV_Optional_Field` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF08_Base64_Embed_PDF_and_Image_in_Plain_XML` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF02_Convert_JSON_to_XML` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF03_Convert_XML_to_CSV` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF04_Convert_CSV_with header_to_XML` | package `10 - Message Converters Encoding and Decoding` | runtime `STARTED` | risks: 1
- `IR10_IF01_Convert_XML_to_JSON_Root_Suppress` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF01_Convert_XML_to_JSON` | package `10 - Message Converters Encoding and Decoding` | runtime `STARTED` | risks: 1
- `IR10_IF01_Convert_XML_to_JSON_Array` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF03_Convert_XML_to_CSV_with_parent` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF02_Convert_JSON_to_XML_without_root` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF04_Convert_CSV_to_XML_exclude_active` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF05_Base64_Encoder_Step` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF10_Base64_Groovy_Mapping_Decode_Bytes_to_Property_and_Body` | package `10 - Message Converters Encoding and Decoding` | risks: 3
- `IR10_IF03_Convert_XML_to_CSV_with_Attributes` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF01_Convert_XML_to_JSON_with_Namespace` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF09_Base64_use_Groovy_Embed_PDF_and_Image_in_XML_and_JSON` | package `10 - Message Converters Encoding and Decoding` | risks: 3
- `IR10_IF06_Base64_Decoder_Step` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF02_Convert_JSON_to_XML_with_Namespace` | package `10 - Message Converters Encoding and Decoding` | risks: 2
- `IR10_IF02_Convert_JSON_to_XML_no_root_namespace` | package `10 - Message Converters Encoding and Decoding` | risks: 2
