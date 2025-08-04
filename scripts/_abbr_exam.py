exam_raw_version = "Vår 2023"
exam_raw_version = "CAPQuiz Øving 1"
exam_raw_version = "Kont 2022"
exam_raw_version = str(exam_raw_version).strip().upper()


if exam_raw_version[0] in ["V", "H", "K"]:
        version_abbr = exam_raw_version[0].upper() + exam_raw_version[-2:]
else:
    version_abbr = exam_raw_version[8:]

print(version_abbr)