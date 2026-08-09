import os
import random
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

STATUS_CONFIRMADO = "confirmado"
STATUS_TALVEZ = "talvez"
STATUS_DESISTIU = "desistiu"


class Evento:
    def __init__(self, titulo: str, data_hora: str, vagas: int | None):
        self.titulo = titulo
        self.data_hora = data_hora
        self.vagas = vagas
        self.participantes: dict[int, str] = {}

    def set_status(self, user_id: int, status: str) -> bool:
        if status == STATUS_DESISTIU:
            self.participantes.pop(user_id, None)
            return True
        if status == STATUS_CONFIRMADO and self.vagas is not None:
            confirmados = sum(1 for s in self.participantes.values() if s == STATUS_CONFIRMADO)
            ja_confirmado = self.participantes.get(user_id) == STATUS_CONFIRMADO
            if not ja_confirmado and confirmados >= self.vagas:
                return False
        self.participantes[user_id] = status
        return True

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"🎮 {self.titulo}", color=discord.Color.blurple())
        embed.add_field(name="🗓️ Data/Hora", value=self.data_hora, inline=False)
        if self.vagas is not None:
            confirmados = sum(1 for s in self.participantes.values() if s == STATUS_CONFIRMADO)
            embed.add_field(name="🎟️ Vagas", value=f"{confirmados}/{self.vagas}", inline=False)

        confirmados = [f"<@{uid}>" for uid, s in self.participantes.items() if s == STATUS_CONFIRMADO]
        talvez = [f"<@{uid}>" for uid, s in self.participantes.items() if s == STATUS_TALVEZ]

        embed.add_field(name=f"✅ Confirmados ({len(confirmados)})", value="\n".join(confirmados) or "—", inline=True)
        embed.add_field(name=f"❔ Talvez ({len(talvez)})", value="\n".join(talvez) or "—", inline=True)
        return embed


eventos: dict[int, Evento] = {}


class EventoView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id

    async def _atualizar(self, interaction: discord.Interaction, status: str):
        evento = eventos.get(self.message_id)
        if evento is None:
            await interaction.response.send_message("Evento não encontrado.", ephemeral=True)
            return

        ok = evento.set_status(interaction.user.id, status)
        if not ok:
            await interaction.response.send_message("Vagas esgotadas.", ephemeral=True)
            return

        await interaction.response.edit_message(embed=evento.build_embed(), view=self)

    @discord.ui.button(label="Confirmado", style=discord.ButtonStyle.success, custom_id="evento_confirmado")
    async def confirmado(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._atualizar(interaction, STATUS_CONFIRMADO)

    @discord.ui.button(label="Talvez", style=discord.ButtonStyle.secondary, custom_id="evento_talvez")
    async def talvez(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._atualizar(interaction, STATUS_TALVEZ)

    @discord.ui.button(label="Desistir", style=discord.ButtonStyle.danger, custom_id="evento_desistir")
    async def desistir(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._atualizar(interaction, STATUS_DESISTIU)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot online: {bot.user}")


@bot.tree.command(name="criar-evento", description="Cria um evento com inscrição por botões")
@app_commands.describe(titulo="Título do evento", data_hora="Data e hora do evento", vagas="Número de vagas (opcional)")
async def criar_evento(interaction: discord.Interaction, titulo: str, data_hora: str, vagas: int | None = None):
    if vagas is not None and vagas <= 0:
        await interaction.response.send_message("Vagas deve ser maior que zero.", ephemeral=True)
        return

    evento = Evento(titulo, data_hora, vagas)
    await interaction.response.send_message(embed=evento.build_embed())
    message = await interaction.original_response()

    view = EventoView(message.id)
    eventos[message.id] = evento
    await message.edit(view=view)


@bot.tree.command(name="sortear-times", description="Divide os membros do seu canal de voz em 2 times")
async def sortear_times(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or interaction.user.voice is None:
        await interaction.response.send_message("Você precisa estar em um canal de voz.", ephemeral=True)
        return

    canal = interaction.user.voice.channel
    membros = [m for m in canal.members if not m.bot]

    if len(membros) < 2:
        await interaction.response.send_message("São necessários pelo menos 2 membros no canal.", ephemeral=True)
        return

    random.shuffle(membros)
    metade = len(membros) // 2 + len(membros) % 2
    time_a = membros[:metade]
    time_b = membros[metade:]

    embed = discord.Embed(title="⚔️ Sorteio de Times", color=discord.Color.gold())
    embed.add_field(name=f"🔵 Time A ({len(time_a)})", value="\n".join(m.mention for m in time_a) or "—", inline=True)
    embed.add_field(name=f"🔴 Time B ({len(time_b)})", value="\n".join(m.mention for m in time_b) or "—", inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = "Ocorreu um erro ao executar o comando."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    bot.run(TOKEN)
