from task_processing import get_topics_from_json, enum_to_str, get_topic_from_enum
from enum import Enum

subject = "IFYKJX1000"

topic_enum = get_topics_from_json(subject)

print(f"Topics for {subject}:")
cur_topic_enum_str = enum_to_str(topic_enum)
print(cur_topic_enum_str)




n = "1"
print(f"Topic for {subject} with value {n}: {get_topic_from_enum(topic_enum, int(n))}")
