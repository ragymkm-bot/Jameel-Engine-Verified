import json
import time

class EventBus:
    def __init__(self):
        self.listeners = {}

    def publish(self, topic, message):
        if topic in self.listeners:
            for callback in self.listeners[topic]:
                callback(message)

    def subscribe(self, topic, callback):
        if topic not in self.listeners:
            self.listeners[topic] = []
        self.listeners[topic].append(callback)

# تجربة الأداء (محاكاة)
bus = EventBus()
def handle_event(msg): pass
bus.subscribe("task", handle_event)

start = time.time()
for _ in range(1000):
    bus.publish("task", "test")
end = time.time()
print(f"Event Bus Performance: {end - start:.4f} seconds for 1000 events")
