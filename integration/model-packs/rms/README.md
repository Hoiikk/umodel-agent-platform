# RMS semantic model

This first pack models only data RMS currently owns: candidates and their
controlled recruitment stage. `position` remains a candidate attribute until
RMS has a separately governed job-opening source. Phone and email are PII and
must not be returned by default to an agent.

Safe read examples:

- Count candidates by `position` and `status`.
- Find candidates in a declared stage and time range.
- Read a candidate's current stage and permitted next actions from RMS.

This pack is read-only. Any future state transition must call the RMS service,
never write through the UModel Connector database account.
