import discord
import itertools

from datetime     import datetime
from discord.ext  import commands
from discord.http import asyncio
from json         import load
from subprocess   import Popen, PIPE, STDOUT
from random       import choice
from time         import time

# Custom help command implementation
class PrettyHelpCommand(commands.DefaultHelpCommand):

    def __init__(self, embedColor, **options):
        self.embedColor = embedColor
        super().__init__(**options)

    async def send_pages(self, note="", inline=False):
        # Overwrite the send method to send each page in an embed instead
        destination = self.get_destination()

        for page in self.paginator.pages:
            formatted = discord.Embed(color=self.embedColor)
            
            split = page.split("**")
            if len(split) == 1:
                formatted.description = page
            else:
                split = iter(split)
                header = next(split)
                formatted.description = header

                for segment in split:
                    if segment.strip() == "":
                        continue
                    
                    title = segment
                    content = next(split)

                    formatted.add_field(name=title, value=content, inline=inline)

            formatted.set_footer(text=note)
            
            await destination.send(" ", embed=formatted)

    def add_indented_commands(self, commands, *, heading, max_size=None):
        if not commands:
            return

        self.paginator.add_line()    
        self.paginator.add_line(heading)
        max_size = max_size or self.get_max_size(commands)

        for command in commands:
            name = command.name
            self.paginator.add_line(self.shorten_text("\u200b  `" + name + "`"))
            self.paginator.add_line(self.shorten_text(command.short_doc))

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        if bot.description:
            # <description> portion
            self.paginator.add_line(bot.description, empty=True)

        def get_category(command, *, no_category='\u200b**{0.no_category}**'.format(self)):
            cog = command.cog
            return "**" + cog.qualified_name + '**' if cog is not None else no_category

        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        max_size = self.get_max_size(filtered)
        to_iterate = itertools.groupby(filtered, key=get_category)

        # Now we can add the commands to the page.
        for category, commands in to_iterate:
            commands = sorted(commands, key=lambda c: c.name) if self.sort_commands else list(commands)
            self.add_indented_commands(commands, heading=category, max_size=max_size)

        note = self.get_ending_note()

        await self.send_pages(note=note, inline=True)

    def get_ending_note(self):
        """Returns help command's ending note. This is mainly useful to override for i18n purposes."""
        command_name = self.invoked_with
        return "Type {0}{1} command for more info on a command.".format(self.clean_prefix, command_name)

    def get_command_signature(self, command):
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            fmt = '[%s|%s]' % (command.name, aliases)
            if parent:
                fmt = parent + ' ' + fmt
            alias = fmt
        else:
            alias = command.name if not parent else parent + ' ' + command.name

        return '`%s%s %s`' % (self.clean_prefix, alias, command.signature)

class MetaCog(commands.Cog, name="Other Commands"):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        # Sets up the help command
        bot.help_command = PrettyHelpCommand(bot.embedColor, **dict(paginator=commands.Paginator(prefix="", suffix="")))
        bot.help_command.cog = self

    # Check if the bot is loading
    async def cog_check(self, ctx):
        return not self.bot.loading

    @commands.command()
    @commands.cooldown(2, 5, commands.BucketType.channel)
    async def about(self, ctx):
        """
        Displays bot information.
        """
        aboutEmbed = discord.Embed(title="About", type="rich", colour=self.bot.embedColor, description="ROBOT - Bot for Discord based on the indie game Baba Is You." \
            + f"\nWritten by RocketRace#0798 ({self.bot.get_user(156021301654454272).mention}).")
        aboutEmbed.add_field(name="Github", value="[GitHub repository](https://github.com/RocketRace/robot-is-you)")
        stats = "".join([
            f"\nGuilds: {len(self.bot.guilds)}",
            f"\nUsers: {len(self.bot.users)}",
            f"\nEmoji: {len(self.bot.emojis)}"
        ])
        aboutEmbed.add_field(name="Statistics", value=stats)
        await self.bot.send(ctx, " ", embed=aboutEmbed)

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def patchnotes(self, ctx):
        '''
        Most recent major bot updates.
        Visit the github page (in the `about` command) for a full list of commits.
        '''
        with open("patchnotes.txt") as fp:
            await self.bot.send(ctx, "\n".join(["Recent Updates:"] + list(reversed(fp.read().splitlines()))))

    
    @commands.command()
    @commands.cooldown(2, 2, commands.BucketType.channel)
    async def ping(self, ctx):
        '''
        Returns bot latency.
        '''
        await self.bot.send(ctx, f"Latency: {round(self.bot.latency, 3)} seconds")

    @commands.command()
    @commands.cooldown(2, 10, type=commands.BucketType.channel)
    async def invite(self, ctx):
        '''
        Invite the bot to your own server!
        '''
        ID = self.bot.user.id
        permissions = discord.Permissions(permissions=388160)
        invite = discord.utils.oauth_url(client_id=ID, permissions=permissions)
        formatted = f"[Click Here to invite the bot to your guild!]({invite})"
        msg = discord.Embed(title="Invite", colour=self.bot.embedColor, description=formatted)

        msg.add_field(name="Support Server", value="[Click here to join RocketRace's Bots](https://discord.gg/rMX3YPK)\n")
        await self.bot.send(ctx, " ", embed=msg)

    @commands.Cog.listener()
    async def on_disconnect(self):
        start = time()
        try:
            await self.bot.wait_for("ready", timeout=5.0)
        except asyncio.TimeoutError:
            try: 
                await self.bot.wait_for("ready", timeout=25.0)
            except asyncio.TimeoutError:
                err = discord.Embed(
                    title="Disconnect", 
                    type="rich", 
                    description=f"{self.bot.user.mention} has disconnected.", 
                    color=0xff8800)
            else:
                err = discord.Embed(
                    title="Reconnected",
                    type="rich",
                    description=f"{self.bot.user.mention} has reconnected. Downtime: {str(round(time() - start, 2))} seconds.",
                    color=0xffaa00
                )
        else: 
            err = discord.Embed(
                title="Resumed", 
                type="rich", 
                description=f"{self.bot.user.mention} has reconnected. Downtime: {str(round(time() - start, 2))} seconds.", 
                color=0xffff00
            )
        logger = await self.bot.fetch_webhook(594692503014473729)
        await logger.send(content=" ", embed=err)
    
    def cog_unload(self):
        self.bot.help_command = self._original_help_command

def setup(bot):
    bot.add_cog(MetaCog(bot))
