import collections
import json
from copy import deepcopy
from io import BytesIO

import cv2
import discord
import edgeiq
import numpy as np
from PIL import Image
from discord.ext import commands
import imgkit

from bot import generate_user_error_embed, send_traceback


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
    with open("models/{}/alwaysai.model.json".format(model_name), "r") as json_file:
        decoded_data = flatten(json.loads(json_file.read()))

        for key in decoded_data:
            if decoded_data[key] == "":
                decoded_data[key] = None

        return decoded_data


def get_model_by_alias(alias):
    if alias in model_aliases.keys():
        return alias
    return next((model for model, aliases in model_aliases.items() if alias in aliases), None)


def get_model_aliases(model_name):
    if model_name in model_aliases.keys():
        aliases = deepcopy(model_aliases[model_name])
        aliases.append(model_name)
        return aliases
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
    config = imgkit.config(wkhtmltoimage="wkhtmltopdf/bin/wkhtmltoimage.exe")
    options = {"quiet": ""}
    imgkit.from_string(legend_html, "data/legend.png", config=config, options=options)

    # Apply the semantic segmentation mask onto the given image
    results = semantic_segmentation.segment_image(image_array)
    mask = semantic_segmentation.build_image_mask(results.class_map)
    image = edgeiq.blend_images(image_array, mask, 0.5)

    return image, results


class Model(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # TODO Fix Alpha Channel issue
    @commands.command(aliases=["m"])
    async def model(self, ctx, model, confidence=0.5):  # Only functions for Object Detection FOR NOW
        async with ctx.typing():
            await ctx.message.add_reaction("\U0001f50e")
            attachments = ctx.message.attachments

            # Allowing models without aliases to work
            model_from_alias = get_model_by_alias(model)
            model = model if model_from_alias is None else model_from_alias

            category = get_model_info(model)["model_parameters_purpose"]

            if len(attachments) == 0:
                message = "```NoAttachment - please upload an image when running the model command```\n\n" \
                          "In order to upload an image with a message you can:\n" \
                          "1. Paste an image from your clipboard\n" \
                          "2. Click the + button to the left of where you type your message"
                await generate_user_error_embed(ctx, message)
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
                    try:
                        confidence = float(confidence)
                    except (ValueError, TypeError):
                        confidence = 0.5

                    image, results, text = categories[category](model, confidence, img_np)
                    embed_output = "\n**Confidence:** {}".format(confidence)
                    embed_output += "\n\n**Label:** {}".format(text) if text else ""
                elif category in ["PoseEstimation", "SemanticSegmentation"]:
                    image, results = categories[category](model, img_np)
                else:
                    return  # Make fancy message?

                embed_output = "**User ID:** {}\n\n**Model:** {}".format(ctx.author.id, model) + embed_output

                embed = discord.Embed(title="", description=embed_output, colour=0xC63D3D)
                embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
                embed.set_footer(text="Inference time: {} seconds".format(round(results.duration, 5)))

                resized = False

                with Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)) as im:
                    while True:
                        try:
                            # Converting resulting magic for Discord - AAI uses BGR format, Discord uses RGB format
                            output_buffer = BytesIO()
                            im.save(output_buffer, "png")
                            output_buffer.seek(0)
                            # print(sys.getsizeof(output_buffer))

                            disc_image = discord.File(fp=output_buffer, filename="results.png")
                            embed.set_image(url="attachment://results.png")

                            await ctx.send(embed=embed, file=disc_image)

                            if category == "SemanticSegmentation":
                                legend_embed = discord.Embed(title="Legend", colour=0xC63D3D)
                                image_legend = discord.File("data/legend.png")
                                legend_embed.set_image(url="attachment://legend.png")
                                await ctx.send(embed=legend_embed, file=image_legend)

                            break

                        except discord.errors.HTTPException as e:  # Resize until no 413 error
                            if e.status == 413:
                                im = im.resize((round(im.width * 0.7), round(im.height * 0.7)))
                                if not resized:
                                    embed_output += "\n\n*Some time was spent resizing this image for Discord\n" \
                                                    "Inference time is correct for the amount of time AAI took*"
                                    embed.description = embed_output
                                    resized = True
                            else:
                                raise e

        await ctx.message.delete()

    @model.error
    async def model_error(self, ctx, error):
        error_handled = False

        # Singular errors
        if isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
            message = "```MissingModelName - please specify a model name```\n\n" \
                      "For example: `*model alwaysai/enet`\n" \
                      "This will run the `alwaysai/enet` model on the image you sent with the message"
            await generate_user_error_embed(ctx, message)
            error_handled = True

        # Wrapped errors e.g: discord.ext.commands.errors.CommandInvokeError: ... FileNotFoundError: ...
        error = getattr(error, "original", error)

        if isinstance(error, FileNotFoundError):
            message = "```InvalidModelName - please specify a valid model name```\n\n" \
                      "For example: `*model alwaysai/enet`\n" \
                      "You can find all available models by running `*mhelp`"
            await generate_user_error_embed(ctx, message)
            error_handled = True

        if isinstance(error, discord.errors.Forbidden):
            message = "```Error 403 Forbidden - cannot retrieve asset```\n\n" \
                      "Usually occurs if you delete your message while the bot is still running a model.\n\n" \
                      "Can generally be ignored. If something else caused this then please contact " \
                      "the bot developers."
            await generate_user_error_embed(ctx, message)
            error_handled = True

        if isinstance(error, discord.errors.HTTPException):
            if error.status == 404:
                message = "```Error 404 Not Found - Unknown Message```\n\n" \
                          "Usually occurs if you delete your message while the bot is still running a model.\n\n" \
                          "Can generally be ignored. If something else caused this then please contact " \
                          "the bot developers."
                await generate_user_error_embed(ctx, message)
                error_handled = True

        if not error_handled:
            await send_traceback(ctx, error)


def setup(bot):
    bot.add_cog(Model(bot))


with open("data/aliases.json", "r") as json_file:
    model_aliases = json.loads(json_file.read())
