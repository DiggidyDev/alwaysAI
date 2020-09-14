import collections
from copy import deepcopy
from io import BytesIO

import cv2
import discord
import edgeiq
import imgkit
import numpy as np
from PIL import Image
from discord.ext import commands

from bot import send_traceback, read_json, generate_user_error_embed, get_error_message


def flatten(d, parent_key="", sep="_"):
    """
    :param d: Dictionary
    :param parent_key: Not sure - StackOverflow
    :param sep: Separator for nested dicts
    :return: Flattened Dictionary
    """
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
    :return: Dict, contains the data you requested in the same order
    """
    decoded_data = flatten(read_json("models/{}/alwaysai.model.json".format(model_name)))
    for key in decoded_data:
        if decoded_data[key] == "":
            decoded_data[key] = None

    return decoded_data


def get_model_by_alias(alias):
    """
    :param alias: String, model name alias
    :return: String model name or None if one isn't found
    """
    models = read_json("alwaysai.app.json")["models"]
    if alias in models.keys():
        return alias
    return next((model for model, aliases in model_aliases.items() if alias in aliases), None)


def get_model_aliases(model_name):
    """
    :param model_name: String, model name
    :return: List of aliases + model name or None if model has no aliases
    """
    if model_name in model_aliases.keys():
        aliases = deepcopy(model_aliases[model_name])
        aliases.append(model_name)
        return aliases
    return None


class Model(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = imgkit.config(wkhtmltoimage="wkhtmltopdf/bin/wkhtmltoimage.exe")

    @staticmethod
    def detection_base(model, confidence, image_array):
        detector = edgeiq.ObjectDetection(model)  # model example: "alwaysai/res10_300x300_ssd_iter_140000"
        detector.load(engine=edgeiq.Engine.DNN)

        centroid_tracker = edgeiq.CentroidTracker(deregister_frames=100, max_distance=50)
        results = detector.detect_objects(image_array, confidence_level=confidence)
        objects = centroid_tracker.update(results.predictions)

        predictions = []
        for (object_id, prediction) in objects.items():
            prediction.label = "{}: {}".format(prediction.label, object_id)
            predictions.append(prediction)

        image = edgeiq.markup_image(image_array, predictions)

        return image, results, None

    @staticmethod
    def classification_base(model, confidence, image_array):
        classifier = edgeiq.Classification(model)
        classifier.load(engine=edgeiq.Engine.DNN)

        results = classifier.classify_image(image_array, confidence_level=confidence)
        if results.predictions:
            image_text = "{}, {}%".format(results.predictions[0].label.title().strip(),
                                          round(results.predictions[0].confidence * 100, 2))
            label_width, label_height = cv2.getTextSize(image_text, cv2.QT_FONT_NORMAL, 1, 2)[0]
            scale = image_array.shape[1] / label_width

            new_label_width, new_label_height = cv2.getTextSize(image_text, cv2.QT_FONT_NORMAL, scale, 2)[0]
            cv2.putText(image_array,
                        image_text,
                        (0, new_label_height + 5),
                        cv2.QT_FONT_NORMAL,
                        scale,
                        (0, 0, 255),
                        1)

            return image_array, results, image_text
        return image_array, results, None

    @staticmethod
    def pose_base(model, image_array):
        pose_estimator = edgeiq.PoseEstimation(model)
        pose_estimator.load(engine=edgeiq.Engine.DNN)

        results = pose_estimator.estimate(image_array)
        image = results.draw_poses(image_array)

        return image, results

    def semantic_base(self, model, image_array):
        semantic_segmentation = edgeiq.SemanticSegmentation(model)
        semantic_segmentation.load(engine=edgeiq.Engine.DNN)

        # Build legend into image, save it to a file and crop the whitespace
        legend_html = semantic_segmentation.build_legend()

        options = {"quiet": ""}
        imgkit.from_string(legend_html, "data/legend.png", config=self.config, options=options)
        legend_image = Image.open("data/legend.png")
        width, height = legend_image.size
        legend_image.crop((0, 0, 0.61 * width, height)).save("data/legend.png")

        # Apply the semantic segmentation mask onto the given image
        results = semantic_segmentation.segment_image(image_array)
        mask = semantic_segmentation.build_image_mask(results.class_map)
        image = edgeiq.blend_images(image_array, mask, 0.5)

        return image, results

    # TODO Fix Alpha Channel issue
    @commands.command(aliases=["m"])
    async def model(self, ctx, model, confidence):
        async with ctx.typing():
            await ctx.message.add_reaction("\U0001f50e")
            attachments = ctx.message.attachments

            # Allowing models without aliases to work
            model_from_alias = get_model_by_alias(model)
            model = model if model_from_alias is None else model_from_alias

            category = get_model_info(model)["model_parameters_purpose"]

            if len(attachments) == 0:
                await generate_user_error_embed(ctx, await get_error_message("model", "missingAttachment"))
                return

            for img in attachments:  # Iterating through each image in the message - only works for mobile
                # Getting image and converting it to appropriate data type
                img_bytes = await img.read()
                np_arr = np.fromstring(img_bytes, np.uint8)
                img_np = cv2.imdecode(np_arr, 1)

                embed_output = ""

                categories = {
                    "Classification": self.classification_base,
                    "ObjectDetection": self.detection_base,
                    "PoseEstimation": self.pose_base,
                    "SemanticSegmentation": self.semantic_base
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
                    await generate_user_error_embed(ctx, await get_error_message("model", "invalidModelCategory"))

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

        if ctx.message.guild is not None:
            await ctx.message.delete()

    @model.error
    async def model_error(self, ctx, error):
        error_handled = False

        # Singular errors
        if isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
            await generate_user_error_embed(ctx, await get_error_message("model", "missingModelName"))
            error_handled = True

        # Wrapped errors e.g: discord.ext.commands.errors.CommandInvokeError: ... FileNotFoundError: ...
        error = getattr(error, "original", error)

        if isinstance(error, FileNotFoundError):
            await generate_user_error_embed(ctx, await get_error_message("model", "invalidModelName"))
            error_handled = True

        if isinstance(error, discord.errors.Forbidden):
            await generate_user_error_embed(ctx, await get_error_message("general", "error403"))
            error_handled = True

        if isinstance(error, discord.errors.HTTPException):
            if error.status == 404:
                await generate_user_error_embed(ctx, await get_error_message("general", "error404"))
                error_handled = True

        if not error_handled:
            await send_traceback(ctx, error)


def setup(bot):
    bot.add_cog(Model(bot))


model_aliases = read_json("data/aliases.json")
