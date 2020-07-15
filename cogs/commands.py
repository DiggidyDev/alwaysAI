import collections
import json
import re
from io import BytesIO
from subprocess import Popen, PIPE

import cv2
import discord
import edgeiq
import numpy as np
from PIL import Image
from discord.ext import commands


def flatten(d, parent_key="", sep="_"):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def get_model_info(model_name, *req_data):
    """
    :param model_name: String, name for the model you wish to get data on. E.g. 'alwaysai/res10_300x300_ssd_iter_140000'
    :param req_data: String, multiple arguments that are keys for the data you want. E.g. 'website_url'
    :return: List, contains the data you requested in the same order
    """
    with open("models/{}/alwaysai.model.json".format(model_name), "r") as jsonfile:
        encoded_data = jsonfile.read()
        decoded_data = flatten(json.loads(encoded_data))

    if len(req_data) != 0:
        output = [decoded_data[data] for data in req_data if data in decoded_data.keys()]
    else:
        output = decoded_data

    return output


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

    return image, results


def classification_base(model, confidence, image_array):
    classifier = edgeiq.Classification(model)
    classifier.load(engine=edgeiq.Engine.DNN)

    results = classifier.classify_image(image_array, confidence_level=confidence)
    if results.predictions:
        image_text = "{}, {}%".format(results.predictions[0].label.title().strip(),
                                      round(results.predictions[0].confidence * 100, 2))
        cv2.putText(image_array, image_text, (5, 25), cv2.QT_FONT_NORMAL, 0.7, (0, 0, 255), 2)

    return image_array, results


def pose_base(model, image_array):
    pose_estimator = edgeiq.PoseEstimation(model)
    pose_estimator.load(engine=edgeiq.Engine.DNN)

    results = pose_estimator.estimate(image_array)
    image = results.draw_poses(image_array)

    return image, results


def semantic_base(model, image_array):
    semantic_segmentation = edgeiq.SemanticSegmentation(model)
    semantic_segmentation.load(engine=edgeiq.Engine.DNN)

    results = semantic_segmentation.segment_image(image_array)
    mask = semantic_segmentation.build_image_mask(results.class_map)
    image = edgeiq.blend_images(image_array, mask, 0.5)

    return image, results


class Commands(commands.Cog):
    # TODO Add in model list command
    # TODO Install more models
    # TODO Model install command - owner only

    def __init__(self, bot):
        self.bot = bot
        self.bot.docs = None
        self.bot.lookup = None

    def get_docs(self):

        if not self.bot.docs:  # If the find command has already been used, then this acts as a cache, almost - it'll
            # only need to fetch the docs once per boot/reload
            process = Popen(["python", "-m", "sphinx.ext.intersphinx", "https://alwaysai.co/docs/objects.inv"],
                            stdout=PIPE)
            output = process.communicate()

            self.bot.docs = output  # Using a bot variable which will be used to create the lookup dict

        return self.bot.docs

    async def fetch(self, query):
        docs = self.get_docs()

        if not self.bot.lookup:  # Create the lookup dict if it doesn't exist
            self.bot.lookup = {}
            sections = []

            # Doesn't like UTF-8 codec, hence \/
            for section in docs[0].decode("cp1252").split("py:")[1:]:

                sectors = section.split()  # Removing whitespace

                if sectors[0] == "module":
                    sectors = sectors[:sectors.index("std:doc")]  # Chop out extraneous data from the end
                    # TODO: ADD LABELS(?)

                sections.append(" ".join([s for s in sectors]))  # Replacing all of the whitespace with a single space

                links = [i for i in sectors if "/" in i]  # Grab each object's link
                objects = [i for i in sectors if "/" not in i and "." in i]  # Grab each object

                # They're ordered like so with their respective links:
                #
                #    OBJECT.ATTR               #URL.EXT.FOR.OBJECT.ATTR
                #    ANOTHER.OBJECT.ATTR       #URL.EXT.FOR.ANOTHER.OBJECT.ATTR
                #
                #
                # Hence zipping it will group them correctly:
                #
                #    [("OBJECT.ATTR", "#URL.EXT.FOR.OBJECT.ATTR"), (...)]
                meta = zip(objects, links)

                for o, l in meta:
                    self.bot.lookup[o] = "https://alwaysai.co/docs/{}".format(
                        l)  # Assign the object's URL to the object

            self.bot.docs = " ".join(
                sections)  # Concatenating each of the sections: attribute, function, method, module, class

        pattern = re.compile(r"\w*(\.*{}\.*)\w*".format(query), re.IGNORECASE)
        indices = [(i.span()[0], i.span()[1]) for i in pattern.finditer(
            self.bot.docs)]  # Getting the indices of each search result in the sections' concatenation

        # Probably one of the more disgusting lines :/ (I agree, my brain can't process the chaos)
        # Finds the entire word that was found - characters up to the previous and next space.
        # Sorts it alphabetically (and case-sensitively)
        suggestions = sorted(
            {self.bot.docs[self.bot.docs.rfind(" ", 0, pos[0]) + 1:self.bot.docs.find(" ", pos[1])] for pos in indices
             if "/" not in self.bot.docs[self.bot.docs.rfind(" ", 0, pos[0]) + 1:self.bot.docs.find(" ", pos[1])]})

        return suggestions

    @commands.command()
    async def help(self, ctx):
        """
        Just a help command that'll be useful some day soon.
        We should soooo do like *help <cmd> and then show what args each command takes
        It'd look funky - like how Dpys docs are really nice
        Sorry I just reaaaally like the docs
        """
        await ctx.send("~ W.I.P ~")

    @commands.command(aliases=["search"])
    async def find(self, ctx, *, query):
        suggestions = await self.fetch(query)  # Made asynchronous due to subprocess' Popen being a blocking call

        links = [self.bot.lookup[s] for s in suggestions]  # Get each object's link from the lookup dictionary
        # created earlier

        # Removes the preceding edgeiq. from each object
        results = "\n".join(["[`{}`]({})".format(r.replace("edgeiq.", ""), l) for l, r in zip(links, suggestions)])

        # General fancifying of the results
        results_count_true = len(links)
        results_short = results[:results.rfind("[", 0, 2048)] if len(results) > 2048 else results
        results_count = results_short.count("\n") + 1 if len(
            results) <= 2048 and results_count_true != 0 else results_short.count("\n")

        embed = discord.Embed(title="{} Result{}".format(results_count, "s" if results_count != 1 else ""),
                              description=results_short)

        filtered_results = results_count_true - results_count
        if filtered_results > 0:
            embed.set_footer(
                text="{} other result{} found".format(filtered_results, "s" if filtered_results != 1 else ""))

        await ctx.send(embed=embed)

    # TODO Add in nicer error message if user doesn't define a model
    # TODO Add custom error for no image sent
    # TODO Scale down image if image too large ~ "Payload Too Large (error code: 40005): Request entity too large"
    # TODO Fix Alpha Channel issue
    # TODO Add more info for segmentation (colour legend?)
    # TODO Remove confidence from embed if it doesn't matter for the model - PoseEstimation + SemanticSegmentation
    @commands.command()
    async def model(self, ctx, model, confidence=0.5):  # Only functions for Object Detection FOR NOW
        category = get_model_info(model, "model_parameters_purpose")[0]

        for img in ctx.message.attachments:  # Iterating through each image in the message - only works for mobile

            # Getting image and converting it to appropriate data type
            img_bytes = await img.read()
            np_arr = np.fromstring(img_bytes, np.uint8)
            img_np = cv2.imdecode(np_arr, 1)

            if category == "ObjectDetection":
                image, results = detection_base(model, confidence, img_np)
            elif category == "Classification":
                image, results = classification_base(model, confidence, img_np)
            elif category == "PoseEstimation":
                image, results = pose_base(model, img_np)
            elif category == "SemanticSegmentation":
                image, results = semantic_base(model, img_np)
            else:
                return  # Make fancy message?

            # Converting resulting magic for Discord - AAI uses BGR format, Discord uses RGB format
            with Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)) as im:
                output_buffer = BytesIO()
                im.save(output_buffer, "png")
                output_buffer.seek(0)

            disc_image = discord.File(fp=output_buffer, filename="results.png")

            embed = discord.Embed(title="",
                                  description="**User ID:** {}\n\n"
                                              "**Model:** {}\n"
                                              "**Confidence:** {}".format(ctx.author.id, model, confidence),
                                  colour=0xC63D3D)
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
            embed.set_image(url="attachment://results.png")
            embed.set_footer(text="Inference time: {} seconds".format(round(results.duration, 5)))
            await ctx.send(embed=embed, file=disc_image)

        await ctx.message.delete()  # TODO Maybe move this - actually its probably best here...


def setup(bot):
    bot.add_cog(Commands(bot))
