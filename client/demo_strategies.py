import asyncio, server


async def gmail_unread_promotions_last_3_months():
  await server.rpc('navigate', url='https://mail.google.com/mail/u/0/#inbox')
  await server.rpc('wait_for_selector', selector='div[role=main]')
  # Click Promotions tab if present
  try:
    await server.rpc('click', selector='div[role=tab] [aria-label^="Promotions"]')
  except Exception:
    pass
  await server.rpc('wait_for_selector', selector='table[role=grid]')
  snap = await server.rpc('read_viewport')
  print(snap['text'][:2000])

async def papers_ui_agents_latest():
  await server.rpc('navigate', url='https://huggingface.co/papers')
  await server.rpc('wait_for_selector', selector='input[type=search]')
  await server.rpc('type', selector='input[type=search]', text='UI Agents', clear=True)
  await server.rpc('press_key', key='Enter')
  await server.rpc('wait_for_selector', selector='article a[href^="/papers/"]')
  titles = await server.rpc('query_text', selector='article h3', all=True, max=5)
  print('Top results:', titles['values'])

async def main():
    # Start server and wait for Chrome extension
    server_task = asyncio.create_task(server.run_server())
    try:
        await server.wait_for_extension(timeout=20)
        await gmail_unread_promotions_last_3_months()
    finally:
        server_task.cancel()

# Run main
asyncio.run(main())