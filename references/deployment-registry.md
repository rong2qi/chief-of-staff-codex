# Deployment registry

Keep cloud deployment inventory in `.chief-of-staff/deployment-registry.json`, separately from the control plane and task registry. Each entry identifies the provider, environment, target, status, evidence, and any approval reference.

The registry is never an execution credential or standing authorization. Production deployment, production change, release, rollback, payment, external notification, and permission expansion each need their own explicit user approval immediately before the operation.
