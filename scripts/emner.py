import asyncio
import prompttotext

# Bygg opp emnekart fra tekstfil
emnekart = {}
with open("ntnu_emner.txt", encoding="utf-8") as f:
    for linje in f:
        deler = linje.strip().split("\t")
        if len(deler) >= 2:
            emnekode = deler[0]
            emnenavn = deler[1]
            emnekart[emnekode] = emnenavn

# Emnekode du vil spørre om
print(emnekart["IMAT2022"])

async def test_prompt():
    prompt = f"Hva er temaene i emnet {emnekart['IMAT2022']}?"
    result = await prompttotext.async_prompt_to_text(
        prompt,
        max_tokens=1000,
        isNum=False,
        maxLen=2000
    )
    print(result)

if __name__ == "__main__":
    asyncio.run(test_prompt())
