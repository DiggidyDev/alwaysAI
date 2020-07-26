# alwaysAI
The unofficial official alwaysAI discord bot repo!

## Dependencies
* discord.py
* Pillow
* psutil
* sphinx
* imgkit
* [wkhtmltoimage.exe](https://wkhtmltopdf.org/downloads.html)

## Setup
Add in the data folder a `token.secret` file put within it the bots token.

Add the downloaded `wkhtmltoimage.exe` to `/wkhtmltopdf`.

To start running the bot run `run.bat`.

## Data Folder Info
### Don't modify
**png** - images used for embeds

**help.json** - data used by the help embed

### Can modify
**aliases.json** - model aliases. Feel free to add to this file any new models or new custom aliases.

**admins.json** - Discord IDs for people you want to be able to use: `*sys`, `*cog` and `*eval`.
