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
        # Getting image and converting it to appropriate data type
        img_bytes = await ctx.message.attachments[0].read()  # TODO Run the model for multiple images
        nparr = np.fromstring(img_bytes, np.uint8)
        img_np = cv2.imdecode(nparr, 1)

        # Copy paste
        obj_detect = edgeiq.ObjectDetection("alwaysai/res10_300x300_ssd_iter_140000")  # Todo use specified model
        obj_detect.load(engine=edgeiq.Engine.DNN)
        centroid_tracker = edgeiq.CentroidTracker(deregister_frames=100, max_distance=50)

        results = obj_detect.detect_objects(img_np, confidence_level=.5)
        objects = centroid_tracker.update(results.predictions)

        predictions = []
        for (object_id, prediction) in objects.items():
            prediction.label = "face {}".format(object_id)
            predictions.append(prediction)

        image = edgeiq.markup_image(img_np, predictions)

        # TODO Run the model for multiple images
        # TODO Find a way to send bytes img to Discord
        await ctx.send(file=None)


def setup(bot):
    bot.add_cog(Commands(bot))
