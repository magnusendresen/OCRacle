checked_tasks = 5

# Iterer over de første `checked_tasks` oppgavene
for i in range(0, checked_tasks):
    if i == 0: # Dersom oppgaven er valid, anta at de neste også er det
        continue
    print(i)

# Iterer over de siste `checked_tasks` oppgavene i omvendt rekkefølge
for i in range(-1, -checked_tasks -1, -1):
    if i == -1: # Dersom oppgaven er valid, anta at de neste også er det
        continue
    print(i)