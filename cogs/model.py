import collections
import json
from io import BytesIO

import cv2
import discord
import edgeiq
import numpy as np
from PIL import Image
from discord.ext import commands
import imgkit


def flatten(d, parent_key="", sep="_"):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def get_model_info(model_name):
    """
    :param model_name: String, name for the model you wish to get data on. E.g. 'alwaysai/res10_300x300_ssd_iter_140000'
    :return Dict, contains the data you requested in the same order
    """
    with open("models/{}/alwaysai.model.json".format(model_name), "r") as jsonfile:
        encoded_data = jsonfile.read()
        decoded_data = flatten(json.loads(encoded_data))

        for key in decoded_data:
            if decoded_data[key] == "":
                decoded_data[key] = None

        return decoded_data


def get_model_by_alias(alias):
    aliases = {
        ("alwaysai/agenet", "agenet", "age"): "alwaysai/agenet",
        ("alwaysai/enet", "enet"): "alwaysai/enet",
        ("alwaysai/fcn_resnet18_cityscapes_512x256",
         "fcn_resnet18_cityscapes_512x256", "cityscapes", "city",
         "cities"): "alwaysai/fcn_resnet18_cityscapes_512x256",
        ("alwaysai/human-pose", "human", "human-pose", "human_pose",
         "pose"): "alwaysai/human-pose",
        ("alwaysai/res10_300x300_ssd_iter_140000",
         "res10_300x300_ssd_iter_140000", "res10", "iter", "iter_ssd",
         "ssd_iter"): "alwaysai/res10_300x300_ssd_iter_140000",
        ("alwaysai/ssd_mobilenet_v2_oidv4", "ssd_mobilenet_v2_oidv4",
         "mobilenet", "ssd_mobile", "mobile",
         "mobilenet_ssd"): "alwaysai/ssd_mobilenet_v2_oidv4"
    }

    for a, m in aliases.items():
        if alias in a:
            return m

    return None


def detection_base(model, confidence, image_array):
    detector = edgeiq.ObjectDetection(model)  # model example: "alwaysai/res10_300x300_ssd_iter_140000"
    detector.load(engine=edgeiq.Engine.DNN)

    centroid_tracker = edgeiq.CentroidTracker(deregister_frames=100, max_distance=50)
    results = detector.detect_objects(image_array, confidence_level=confidence)
    objects = centroid_tracker.update(results.predictions)

    predictions = []
    for (object_id, prediction) in objects.items():
        prediction.label = "Object {}".format(object_id)
        predictions.append(prediction)

    image = edgeiq.markup_image(image_array, predictions)

    return image, results, None


# TODO Make font scale with image size - look into getTextSize() potentially for width of text
def classification_base(model, confidence, image_array):
    classifier = edgeiq.Classification(model)
    classifier.load(engine=edgeiq.Engine.DNN)

    results = classifier.classify_image(image_array, confidence_level=confidence)
    if results.predictions:
        image_text = "{}, {}%".format(results.predictions[0].label.title().strip(),
                                      round(results.predictions[0].confidence * 100, 2))
        cv2.putText(image_array, image_text, (5, 25), cv2.QT_FONT_NORMAL, 0.7, (0, 0, 255), 2)

        return image_array, results, image_text
    return image_array, results, None


def pose_base(model, image_array):
    pose_estimator = edgeiq.PoseEstimation(model)
    pose_estimator.load(engine=edgeiq.Engine.DNN)

    results = pose_estimator.estimate(image_array)
    image = results.draw_poses(image_array)

    return image, results


# TODO Find a way to show the legend - maybe HTML -> PNG and then combine the image with that?
def semantic_base(model, image_array):
    semantic_segmentation = edgeiq.SemanticSegmentation(model)
    semantic_segmentation.load(engine=edgeiq.Engine.DNN)

    # Build legend into image and save it to a file
    legend_html = semantic_segmentation.build_legend()
    pathtoexe = "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltoimage.exe"
    config = imgkit.config(wkhtmltoimage=pathtoexe)
    imgkit.from_string(legend_html, "legend.png", config=config)

    # Apply the semantic segmentation mask onto the given image
    results = semantic_segmentation.segment_image(image_array)
    mask = semantic_segmentation.build_image_mask(results.class_map)
    image = edgeiq.blend_images(image_array, mask, 0.5)

    return image, results


class Model(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        # Discord errors
        if isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
            await ctx.send("`ERROR: MissingRequiredArgument - please specify a model name.`")

        # Wrapped errors e.g:
        # discord.ext.commands.errors.CommandInvokeError: Command raised an exception: FileNotFoundError: [Errno 2] No
        # such file or directory: 'example.json'
        
        error = getattr(error, "original", error)

        if isinstance(error, FileNotFoundError):
            await ctx.send("`ERROR: MissingModelName - please specify a valid model name.`")

    # TODO Add in nicer error message if user doesn't define a model
    # TODO Add custom error for no image sent
    # TODO Scale down image if image too large ~ "Payload Too Large (error code: 40005): Request entity too large"
    # TODO Fix Alpha Channel issue
    @commands.command()
    async def model(self, ctx, model, confidence=0.5):  # Only functions for Object Detection FOR NOW
        async with ctx.typing():
            attachments = ctx.message.attachments
            model = get_model_by_alias(model)
            category = get_model_info(model)["model_parameters_purpose"]

            if len(attachments) == 0:
                await ctx.send("`ERROR: NoAttachment - upload an image with the command.`")
                return

            for img in attachments:  # Iterating through each image in the message - only works for mobile

                # Getting image and converting it to appropriate data type
                img_bytes = await img.read()
                np_arr = np.fromstring(img_bytes, np.uint8)
                img_np = cv2.imdecode(np_arr, 1)

                embed_output = ""

                categories = {
                    "Classification": classification_base,
                    "ObjectDetection": detection_base,
                    "PoseEstimation": pose_base,
                    "SemanticSegmentation": semantic_base
                }

                if category in ["ObjectDetection", "Classification"]:
                    image, results, text = categories[category](model, confidence, img_np)
                    embed_output = "\n**Confidence:** {}".format(confidence)
                    embed_output += "\n\n**Label:** {}".format(text) if text else ""
                elif category in ["PoseEstimation", "SemanticSegmentation"]:
                    image, results = categories[category](model, img_np)
                else:
                    return  # Make fancy message?

                embed_output = "**User ID:** {}\n\n**Model:** {}".format(ctx.author.id, model) + embed_output

                # Converting resulting magic for Discord - AAI uses BGR format, Discord uses RGB format
                with Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)) as im:
                    output_buffer = BytesIO()
                    im.save(output_buffer, "png")
                    output_buffer.seek(0)

                image_disc = discord.File(fp=output_buffer, filename="results.png")

                embed = discord.Embed(title="", description=embed_output, colour=0xC63D3D)
                embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
                embed.set_image(url="attachment://results.png")
                embed.set_footer(text="Inference time: {} seconds".format(round(results.duration, 5)))

            await ctx.message.delete()
            await ctx.send(embed=embed, file=image_disc)
            if category == "SemanticSegmentation":

                legend_embed = discord.Embed(title="Legend", colour=0xC63D3D)
                image_legend = discord.File("legend.png")
                legend_embed.set_image(url="attachment://legend.png")

                await ctx.send(embed=legend_embed, file=image_legend)


def setup(bot):
    bot.add_cog(Model(bot))
