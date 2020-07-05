import cv2
import edgeiq
from bot import Bot


def main():
    # Your alwaysAI app goes here!
    print("This is a stub of an alwaysAI application")


if __name__ == "__main__":
    bot = Bot()
    bot.remove_command("help")
    bot.load_cog("cogs.owner")
    bot.load_cog("cogs.commands")
    bot.load_cog("cogs.events")
    bot.run()
