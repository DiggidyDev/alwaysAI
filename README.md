# alwaysAI
The unofficial official alwaysAI discord bot repo!

## Dependencies (most within requirements.txt)
* discord.py
* Pillow
* psutil
* sphinx
* imgkit
* [wkhtmltoimage.exe](https://wkhtmltopdf.org/downloads.html)

## Data Folder Info
### Don't modify
**png** - images used for embeds

**help.json** - data used by the help embed

### Can modify
**aliases.json** - model aliases. Feel free to add to this file any new models or new custom aliases.

**admins.json** - Discord IDs for people you want to be able to use: `*sys`, `*cog` and `*eval`.


## Setup
1. Add in the data folder a `token.secret` file put within it the bots token. It is essentially just a text file with a different extension.
2. Run the `[wkhtmltoimage.exe](https://wkhtmltopdf.org/downloads.html)` installer and install it into a folder called wkhtmltopdf. The path to `wkhtmltoimage.exe` should be `repoPath/wkhtmltopdf/bin/wkhtmltoimage.exe`
3. Run in terminal in the repo `aai user login` and provide the right details
4. On the [alwaysai website](https://alwaysai.co/dashboard/) create a new project from scratch.
5. Run in terminal in the repo `aai app configure --project <Project ID>` where `<Project ID>` is the Project ID provided on your project page and select `Your local computer`
6. Run in terminal in the repo `aai app install` to get the Python venv and appropriate models
7. Run in terminal in the repo `cd venv/scripts`
8. Run in terminal in the repo `activate`
9. Run in terminal in the repo `pip install -r ../../data/requirements.txt`

To start running the bot run `run.bat`.


