import traceback

from discord.ext import commands

bot = commands.Bot(command_prefix="a!")

cogs = [
    "cogs.commands",
    "cogs.events",
    "cogs.owner"
]

@bot.event
async def on_ready():
    print("Ready :^)")


if __name__ == "__main__":
    for i, cog in enumerate(cogs, 1):
        try:
            bot.load_extension(cog)
            print(f"{i}/{len(cogs)}: {cog.split('.')[1].title()}.py successfully loaded!")
        except:
            traceback.print_exc()

bot.run("TOKEN")
