from pyrogram import Client, filters

API_ID = 24203893
API_HASH = "6ba29d5fb7d359fe9afb138ea89873b4"
STRING_SESSION = "BAFxUnUAT9x61l0RT1tnOI7CiKRiUUtYpL7hxyoR5MlELoRWN8diwKefEvqh_TGdngltRTovxh3ngMbYFryG5yviJEDPXsVKJVugzkZcXCbFr8AVNqL_oLhSluUarbXR4C7jOpld5q6VwV2Rql0CruHtLGObiNmnxT9nro0dmaea4owI6nGbKb6X5AtDeibwS_BWxmVLc8VYuyAAcXbQwpTvEPgtVOBSi3sKwSml7H7CpwnVHwlG9JS-4SX9_xg8Uq2rnVd89m4M0_IgOHSDQoWSTVfSyCFdIu4GBWXudul7aWwZUZQShLSjzQtqRURP8pSLhXi0ZJR4p-yFJRzdoikxRzYhpwAAAAG243VNAA"

BOT_USERNAME = "ris_bottetris_bottetris_bot"  # 👈 yaha apne bot ka username daalna hai

app = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION
)

@app.on_message(filters.private & filters.text)
async def create_group(client, message):
    try:
        if message.text.lower().startswith("/setup"):
            # Command ke baad ka text group name banega
            parts = message.text.split(" ", 1)
            if len(parts) > 1:
                chat_title = parts[1]  # user ne jo group name diya
            else:
                chat_title = f"Escrow Deal - {message.from_user.first_name}"  # default

            # Step 1: Create group
            group = await client.create_supergroup(chat_title, "Private escrow group auto-created")

            # Step 2: Add user
            await client.add_chat_members(group.id, [message.from_user.id])

            # Step 3: Invite link
            link = await client.export_chat_invite_link(group.id)

            # Step 4: Try to add your bot
            try:
                await client.add_chat_members(group.id, [BOT_USERNAME])
                bot_status = f"🤖 Bot @{BOT_USERNAME} successfully added!"
            except Exception as e:
                bot_status = (f"⚠️ Bot ko direct add nahi kar paya: {str(e)}\n"
                              f"Aap manually is link se bot add karen: {link}")

            # Step 5: Confirmation
            await message.reply_text(
                f"✅ New private escrow group created:\n"
                f"📛 {chat_title}\n"
                f"🔗 {link}\n\n{bot_status}"
            )

        elif message.text.lower() in ["deal", "/create"]:
            chat_title = f"Escrow Deal - {message.from_user.first_name}"

            # Step 1: Create group
            group = await client.create_supergroup(chat_title, "Private escrow group auto-created")

            # Step 2: Add user
            await client.add_chat_members(group.id, [message.from_user.id])

            # Step 3: Invite link
            link = await client.export_chat_invite_link(group.id)

            # Step 4: Try to add your bot
            try:
                await client.add_chat_members(group.id, [BOT_USERNAME])
                bot_status = f"🤖 Bot @{BOT_USERNAME} successfully added!"
            except Exception as e:
                bot_status = (f"⚠️ Bot ko direct add nahi kar paya: {str(e)}\n"
                              f"Aap manually is link se bot add karen: {link}")

            # Step 5: Confirmation
            await message.reply_text(
                f"✅ New private escrow group created:\n"
                f"📛 {chat_title}\n"
                f"🔗 {link}\n\n{bot_status}"
            )

        else:
            await message.reply_text("Type '/setup GroupName' or 'deal' to create a new escrow group.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

print("🚀 Userbot running...")
app.run()        
