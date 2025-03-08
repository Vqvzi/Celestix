import discord
from discord.ext import commands, tasks
import sqlite3
import datetime

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("database/celestix.db")
        self.cursor = self.conn.cursor()
        self._initialize_db()

    def _initialize_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                coins INTEGER DEFAULT 0,
                prestige INTEGER DEFAULT 0
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rewards (
                level INTEGER PRIMARY KEY,
                reward_type TEXT,
                reward_value TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS shop (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT,
                item_price INTEGER,
                item_role TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS season (
                season_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'inaktive'
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                start_date TEXT,
                end_date TEXT,
                reward TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,  -- Name des Achievements
                description TEXT,  -- Beschreibung des Achievements
                condition TEXT,  -- Bedingung (z. B. "prestige >= 1", "level >= 25")
                reward TEXT  -- Belohnung (z. B. "500 Coins", "Exklusive Rolle")
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id INTEGER,
                achievement_id INTEGER,
                completed BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (user_id, achievement_id)
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS weekly_challenges (
                challenge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                condition TEXT,  -- Bedingung (z. B. "messages >= 100")
                reward TEXT  -- Belohnung (z. B. "1000 Coins")
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_weekly_progress (
                user_id INTEGER,
                challenge_id INTEGER,
                progress INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, challenge_id)
            )
        """)
        self.conn.commit()
    
    @tasks.loop(hours=1)
    async def check_season(self):
        season = self.cursor.execute("SELECT end_date FROM season WHERE status = 'active'").fetchone()
        if season:
            end_date = datetime.datetime.fromisoformat(season[0])
            if datetime.datetime.now() >= end_date:
                self.cursor.execute("UPDATE season SET status = 'ended' WHERE status = 'active'")
                self.conn.commit()
                print("Season wurde automatisch beendet.")
                
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Überprüfe, ob eine aktive Season läuft
        season = self.cursor.execute("SELECT status FROM season WHERE status = 'active'").fetchone()
        if not season:
            return  # Keine aktive Season, kein XP

        user_id = message.author.id
        self.cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        self.cursor.execute("UPDATE users SET xp = xp + 10 WHERE user_id = ?", (user_id,))
        self.conn.commit()

        xp, level = self.cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,)).fetchone()
        xp_needed = level * 100

        if xp >= xp_needed:
            self.cursor.execute("UPDATE users SET level = level + 1, xp = 0 WHERE user_id = ?", (user_id,))
            self.conn.commit()
            await self._give_reward(message.author, level + 1)
        
        await self.check_achievements(user_id)
        await self.update_weekly_progress(user_id)

    async def _give_reward(self, user, level):
        reward = self.cursor.execute("SELECT reward_type, reward_value FROM rewards WHERE level = ?", (level,)).fetchone()
        if reward:
            reward_type, reward_value = reward
            if reward_type == "role":
                role = discord.utils.get(user.guild.roles, id=int(reward_value))
                if role:
                    await user.add_roles(role)
                    await user.send(f"Glückwunsch! Du hast Level {level} erreicht und die Rolle {role.name} erhalten!")
            elif reward_type == "coins":
                self.cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (int(reward_value), user.id))
                self.conn.commit()
                await user.send(f"Glückwunsch! Du hast Level {level} erreicht und {reward_value} Coins erhalten!")
            elif reward_type == "channel":
                channel = discord.utils.get(user.guild.channels, id=int(reward_value))
                if channel:
                    await channel.set_permissions(user, read_messages=True)
                    await user.send(f"Glückwunsch! Du hast Level {level} erreicht und Zugriff auf den Channel {channel.name} erhalten!")
            elif reward_type == "badge":
                await user.send(f"Glückwunsch! Du hast Level {level} erreicht und ein exklusives Badge erhalten!")

    async def check_achievements(self, user_id):
        achievements = self.cursor.execute("SELECT achievement_id, condition FROM achievements").fetchall()
        user_data = self.cursor.execute("SELECT level, prestige FROM users WHERE user_id = ?", (user_id,)).fetchone()

        if not user_data:
            return

        level, prestige = user_data

        for achievement_id, condition in achievements:
            if eval(condition):  # Bedingung auswerten (z. B. "prestige >= 1")
                self.cursor.execute("INSERT OR REPLACE INTO user_achievements (user_id, achievement_id, completed) VALUES (?, ?, TRUE)", (user_id, achievement_id))
                self.conn.commit()

    async def update_weekly_progress(self, user_id):
        challenges = self.cursor.execute("SELECT challenge_id, condition FROM weekly_challenges").fetchall()
        for challenge_id, condition in challenges:
            if "messages" in condition:  # Beispiel: "messages >= 100"
                self.cursor.execute("""
                    INSERT OR IGNORE INTO user_weekly_progress (user_id, challenge_id, progress)
                    VALUES (?, ?, 0)
                """, (user_id, challenge_id))
                self.cursor.execute("""
                    UPDATE user_weekly_progress
                    SET progress = progress + 1
                    WHERE user_id = ? AND challenge_id = ?
                """, (user_id, challenge_id))
                self.conn.commit()

    @discord.slash_command(name="prestige", description="Setze dein Level zurück und erhalte Prestige-Belohnungen")
    async def prestige(self, ctx):
        user_id = ctx.author.id
        level, prestige = self.cursor.execute("SELECT level, prestige FROM users WHERE user_id = ?", (user_id,)).fetchone()

        if level < 55:
            await ctx.respond(f"{ctx.author.mention}, du musst Level 55 erreichen, um das Prestige-System zu nutzen!")
            return

        self.cursor.execute("UPDATE users SET level = 1, xp = 0, prestige = prestige + 1 WHERE user_id = ?", (user_id,))
        self.conn.commit()

        await ctx.respond(f"{ctx.author.mention}, du hast dein Level zurückgesetzt und bist jetzt Prestige {prestige + 1}!")

    @discord.slash_command(name="add_reward", description="Füge eine Belohnung für ein bestimmtes Level hinzu")
    @commands.has_permissions(administrator=True)
    async def add_reward(self, ctx, level: int, reward_type: str, reward_value: str):
        self.cursor.execute("INSERT OR REPLACE INTO rewards (level, reward_type, reward_value) VALUES (?, ?, ?)", (level, reward_type, reward_value))
        self.conn.commit()
        await ctx.respond(f"Belohnung für Level {level} hinzugefügt: {reward_type} ({reward_value})")

    @discord.slash_command(name="shop", description="Zeige den Shop an")
    async def shop(self, ctx):
        items = self.cursor.execute("SELECT item_name, item_price, item_role FROM shop").fetchall()
        if not items:
            await ctx.respond("Der Shop ist leer.")
            return

        response = "**Shop:**\n"
        for item in items:
            response += f"- {item[0]} (Preis: {item[1]} Coins)\n"
        await ctx.respond(response)

    @discord.slash_command(name="buy", description="Kaufe einen Gegenstand aus dem Shop")
    async def buy(self, ctx, item_name: str):
        item = self.cursor.execute("SELECT item_price, item_role FROM shop WHERE item_name = ?", (item_name,)).fetchone()
        if not item:
            await ctx.respond("Dieser Gegenstand existiert nicht.")
            return

        price, role_id = item
        user_coins = self.cursor.execute("SELECT coins FROM users WHERE user_id = ?", (ctx.author.id,)).fetchone()[0]

        if user_coins < price:
            await ctx.respond(f"Du hast nicht genug Coins, um {item_name} zu kaufen.")
            return

        self.cursor.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (price, ctx.author.id))
        self.conn.commit()

        if role_id:
            role = discord.utils.get(ctx.guild.roles, id=int(role_id))
            if role:
                await ctx.author.add_roles(role)
                await ctx.respond(f"Du hast {item_name} gekauft und die Rolle {role.name} erhalten!")
        else:
            await ctx.respond(f"Du hast {item_name} gekauft!")

    @discord.slash_command(name="add_shop_item", description="Füge einen Gegenstand zum Shop hinzu")
    @commands.has_permissions(administrator=True)
    async def add_shop_item(self, ctx, item_name: str, item_price: int, item_role: discord.Role = None):
        self.cursor.execute("INSERT INTO shop (item_name, item_price, item_role) VALUES (?, ?, ?)", (item_name, item_price, item_role.id if item_role else None))
        self.conn.commit()
        await ctx.respond(f"Gegenstand {item_name} zum Shop hinzugefügt!")

    @discord.slash_command(name="remove_shop_item", description="Entferne einen Gegenstand aus dem Shop")
    @commands.has_permissions(administrator=True)
    async def remove_shop_item(self, ctx, item_name: str):
        self.cursor.execute("DELETE FROM shop WHERE item_name = ?", (item_name,))
        self.conn.commit()
        await ctx.respond(f"Gegenstand {item_name} aus dem Shop entfernt!")

    @discord.slash_command(name="pause_season", description="Pausiere die aktuelle Season")
    @commands.has_permissions(administrator=True)

    async def pause_season(self, ctx):
        self.cursor.execute("UPDATE season SET status = 'paused' WHERE status = 'active'")
        self.conn.commit()
        await ctx.respond("Die aktuelle Season wurde pausiert.")

    @discord.slash_command(name="end_season", description="Beende die aktuelle Season")
    @commands.has_permissions(administrator=True)
    async def end_season(self, ctx):
        end_date = datetime.datetime.now().isoformat()
        self.cursor.execute("UPDATE season SET end_date = ?, status = 'ended' WHERE status = 'active'", (end_date,))
        self.conn.commit()
        await ctx.respond("Die aktuelle Season wurde beendet.")
    
    @discord.slash_command(name="rank", description="Zeige dein aktuelles Level und Fortschritt an")
    async def rank(self, ctx):
        user_id = ctx.author.id
        user_data = self.cursor.execute("SELECT xp, level, prestige FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user_data:
            await ctx.respond("Du hast noch keine XP gesammelt.")
            return

        xp, level, prestige = user_data
        xp_needed = level * 100  # Beispiel: 100 XP pro Level
        progress = (xp / xp_needed) * 100  # Fortschritt in Prozent

        # Season-Informationen abrufen
        season = self.cursor.execute("SELECT start_date, end_date, status FROM season ORDER BY season_id DESC LIMIT 1").fetchone()
        if not season:
            season_info = "Es gibt keine aktive Season."
        else:
            start_date, end_date, status = season
            time_left = datetime.datetime.fromisoformat(end_date) - datetime.datetime.now()
            season_info = (
                f"**Season-Status:**\n"
                f"Start: {start_date}\n"
                f"Ende: {end_date}\n"
                f"Status: {status}\n"
                f"Verbleibende Zeit: {time_left.days} Tage und {time_left.seconds // 3600} Stunden."
            )

        await ctx.respond(
            f"**Dein Rang:**\n"
            f"Level: {level}\n"
            f"Prestige: {prestige}\n"
            f"Fortschritt: {progress:.2f}% (XP: {xp}/{xp_needed})\n\n"
            f"{season_info}"
        )

    @discord.slash_command(name="daily", description="Hole deine tägliche Belohnung ab")
    async def daily(self, ctx):
        user_id = ctx.author.id
        last_daily = self.cursor.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if last_daily and last_daily[0]:
            last_daily_date = datetime.datetime.fromisoformat(last_daily[0])
            if (datetime.datetime.now() - last_daily_date).days < 1:
                await ctx.respond("Du hast deine tägliche Belohnung bereits abgeholt. Komme morgen wieder!")
                return

        self.cursor.execute("UPDATE users SET coins = coins + 100, last_daily = ? WHERE user_id = ?", (datetime.datetime.now().isoformat(), user_id))
        self.conn.commit()
        await ctx.respond(f"{ctx.author.mention}, du hast deine tägliche Belohnung von 100 Coins erhalten!")

    @discord.slash_command(name="leaderboard", description="Zeige das Leaderboard an")
    async def leaderboard(self, ctx):
        users = self.cursor.execute("SELECT user_id, level, prestige FROM users ORDER BY level DESC, prestige DESC LIMIT 10").fetchall()
        if not users:
            await ctx.respond("Es gibt noch keine Benutzer im Leaderboard.")
            return

        response = "**Leaderboard:**\n"
        for i, (user_id, level, prestige) in enumerate(users):
            user = await self.bot.fetch_user(user_id)
            response += f"{i + 1}. {user.name} (Level {level}, Prestige {prestige})\n"
        await ctx.respond(response)

    @discord.slash_command(name="start_event", description="Starte ein Event")
    @commands.has_permissions(administrator=True)
    async def start_event(self, ctx, event_name: str, duration_days: int, reward: str):
        start_date = datetime.datetime.now().isoformat()
        end_date = (datetime.datetime.now() + datetime.timedelta(days=duration_days)).isoformat()
        self.cursor.execute("INSERT INTO events (event_name, start_date, end_date, reward) VALUES (?, ?, ?, ?)", (event_name, start_date, end_date, reward))
        self.conn.commit()
        await ctx.respond(f"Event {event_name} gestartet! Es endet in {duration_days} Tagen.")

    @discord.slash_command(name="event_info", description="Zeige Informationen zum aktuellen Event an")
    async def event_info(self, ctx):
        event = self.cursor.execute("SELECT event_name, start_date, end_date, reward FROM events ORDER BY event_id DESC LIMIT 1").fetchone()
        if not event:
            await ctx.respond("Es gibt kein aktives Event.")
            return

        event_name, start_date, end_date, reward = event
        time_left = datetime.datetime.fromisoformat(end_date) - datetime.datetime.now()
        await ctx.respond(
            f"**Event-Info:**\n"
            f"Name: {event_name}\n"
            f"Start: {start_date}\n"
            f"Ende: {end_date}\n"
            f"Belohnung: {reward}\n"
            f"Verbleibende Zeit: {time_left.days} Tage und {time_left.seconds // 3600} Stunden."
        )
    @discord.slash_command(name="achievements", description="Zeige deine Achievements an")
    async def achievements(self, ctx):
        user_id = ctx.author.id

        # Abgeschlossene Achievements
        completed = self.cursor.execute("""
            SELECT a.name, a.description, a.reward
            FROM user_achievements ua
            JOIN achievements a ON ua.achievement_id = a.achievement_id
            WHERE ua.user_id = ? AND ua.completed = TRUE
        """, (user_id,)).fetchall()

        # Offene Achievements
        open_achievements = self.cursor.execute("""
            SELECT a.name, a.description, a.reward
            FROM achievements a
            LEFT JOIN user_achievements ua ON a.achievement_id = ua.achievement_id AND ua.user_id = ?
            WHERE ua.completed IS NULL OR ua.completed = FALSE
        """, (user_id,)).fetchall()

        response = "**Deine Achievements:**\n"
        if completed:
            response += "**Abgeschlossen:**\n"
            for achievement in completed:
                response += f"- **{achievement[0]}**: {achievement[1]} (Belohnung: {achievement[2]})\n"
        else:
            response += "Du hast noch keine Achievements abgeschlossen.\n"

        if open_achievements:
            response += "\n**Offen:**\n"
            for achievement in open_achievements:
                response += f"- **{achievement[0]}**: {achievement[1]} (Belohnung: {achievement[2]})\n"
        else:
            response += "\nDu hast alle Achievements abgeschlossen!"

        await ctx.respond(response)

    @discord.slash_command(name="weekly_challenges", description="Zeige deine wöchentlichen Herausforderungen an")
    async def weekly_challenges(self, ctx):
        user_id = ctx.author.id

        challenges = self.cursor.execute("""
            SELECT wc.name, wc.description, wc.reward, uwp.progress
            FROM weekly_challenges wc
            LEFT JOIN user_weekly_progress uwp ON wc.challenge_id = uwp.challenge_id AND uwp.user_id = ?
        """, (user_id,)).fetchall()

        if not challenges:
            await ctx.respond("Es gibt derzeit keine wöchentlichen Herausforderungen.")
            return

        response = "**Wöchentliche Herausforderungen:**\n"
        for challenge in challenges:
            name, description, reward, progress = challenge
            response += f"- **{name}**: {description} (Fortschritt: {progress})\n"

        await ctx.respond(response)
    
    @discord.slash_command(name="add_achievement", description="Füge ein neues Achievement hinzu")
    @commands.has_permissions(administrator=True)
    async def add_achievement(self, ctx, name: str, description: str, condition: str, reward: str):
    	"""
    	Fügt ein neues Achievement hinzu.
    
    	:param name: Der Name des Achievements (z. B. "Level 25 Meister").
    	:param description: Die Beschreibung des Achievements (z. B. "Erreiche Level 25").
    	:param condition: Die Bedingung, um das Achievement zu erfüllen (z. B. "level >= 25").
    	:param reward: Die Belohnung für das Achievement (z. B. "500 Coins").
    	"""
    	# Füge das Achievement in die Datenbank ein
    	self.cursor.execute("""
    	    INSERT INTO achievements (name, description, condition, reward)
    	    VALUES (?, ?, ?, ?)
    	""", (name, description, condition, reward))
    	self.conn.commit()

    	await ctx.respond(f"Achievement **{name}** wurde hinzugefügt!")

def setup(bot):
    bot.add_cog(XPSystem(bot))