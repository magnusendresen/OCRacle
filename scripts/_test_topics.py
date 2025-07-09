from task_processing import get_topics
from enum import Enum

subject = "IFYX1000"

topic_enum = get_topics(subject)

print(f"Topics for {subject}:")
for topic in topic_enum:
    print(f"{topic.value}: {topic.name}")

def get_topic_from_enum(subject: str, num: int) -> str:
    """Get topic name from enum based on subject and number."""
    topic_enum = get_topics(subject)
    for topic in topic_enum:
        if topic.value == num:
            return topic.name
    return "Unknown Topic"

n = 3
print(f"Topic for {subject} with value {n}: {get_topic_from_enum(subject, n)}")
