from discord.ext import commands
import numpy as np

import cv2
import edgeiq


class Commands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.is_owner()
    @commands.command()
    async def model(self, ctx):
        img_bytes = await ctx.message.attachments[0].read()  # TODO Run the model for multiple images
        nparr = np.fromstring(img_bytes, np.uint8)
        img_np = cv2.imdecode(nparr, 1)


def setup(bot):
    bot.add_cog(Commands(bot))
