from app.engine.status_manager import StatusManager

print(StatusManager.transition("CREATED", "VALIDATED"))

print(StatusManager.transition("VALIDATED", "QUEUED"))

print(StatusManager.transition("SENT", "PROCESSING"))