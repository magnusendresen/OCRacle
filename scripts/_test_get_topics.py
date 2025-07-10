from task_processing import get_topics, enum_to_str, get_topic_from_enum
from enum import Enum

subject = "INGX1002"

topic_enum = get_topics(subject)

print(f"Topics for {subject}:")
cur_topic_enum_str = enum_to_str(topic_enum)
print(cur_topic_enum_str)




n = "3"
print(f"Topic for {subject} with value {n}: {get_topic_from_enum(subject, int(n))}")
