from task_processing import get_topics_from_json, enum_to_str, get_topic_from_enum, get_ignored_topics_from_json
from enum import Enum
import object_handling

subject = "IFYX1000"

ign_topics = get_ignored_topics_from_json(subject)
object_handling.add_topics(subject, "V23", ["Dette er  "], ["Banan"])
if ign_topics is not None and len(ign_topics) > 3:
    ign_topics = f"Ikke inkluder noen temaer som er overhodet knyttet til: {ign_topics} på noen som helst måte."
else:
    ign_topics = ""



print(ign_topics)