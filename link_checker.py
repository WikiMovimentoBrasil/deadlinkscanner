import httpx
import asyncio
import aiohttp
from flask_babel import gettext


async def fetch_pages(session, url, params):
    async with session.get(url, params=params) as response:
        return await response.json()


def get_category_project_and_category_name(category_url):
    return category_url.split('/wiki/', 1)


async def get_pages_in_category(category_url, depth=0, current_level=0):
    category_project, category_name = get_category_project_and_category_name(category_url)
    base_url = category_project + '/w/api.php'

    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category_name,
        "cmlimit": "max",
        "cmnamespace": "0|6|14",
        "cmprop": "title",
        "format": "json"
    }

    pages = []

    async with aiohttp.ClientSession() as session:
        while True:
            data = await fetch_pages(session, base_url, params)

            category_members = data.get('query', {}).get('categorymembers', [])
            if current_level < depth:
                for member in category_members:
                    if member['ns'] == 14:
                        subcategory_url = category_project + "/wiki/" + member['title']
                        subcategory_pages = await get_pages_in_category(subcategory_url, depth, current_level + 1)
                        pages.extend(subcategory_pages)
                    else:
                        pages.append(member)

            pages.extend(category_members)

            if 'continue' in data:
                params.update(data['continue'])
            else:
                break

    return pages


async def fetch_external_links(category_project, page_titles, session):
    base_url = category_project + '/w/api.php'
    params = {
        'action': 'query',
        'titles': page_titles,
        'prop': 'extlinks',
        'format': 'json',
        'ellimit': 'max'
    }

    async with session.get(base_url, params=params) as response:
        data = await response.json()
        pages_ids = data['query']['pages'].keys()
        result_links = {}
        for page_id in pages_ids:
            if '-1' in data['query']['pages'][page_id]:
                result_links[data['query']['pages'][page_id]["title"]] = []  # No page found with this title
            else:
                result_links[data['query']['pages'][page_id]["title"]] = [link["*"] for link in data['query']['pages'][page_id].get('extlinks', []) if "web.archive" not in link["*"]]
        return result_links


async def get_external_links_batch(category_url, page_titles):
    async with aiohttp.ClientSession() as session:
        category_project, category_name = get_category_project_and_category_name(category_url)
        tasks = []

        def chunks(lst):
            for i in range(0, len(lst), 50):
                yield lst[i:i + 50]

        for batch in chunks(page_titles):
            tasks.append(fetch_external_links(category_project, "|".join(batch), session))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results


def get_custom_message(status):
    if 400 <= status < 500:
        if status == 400:
            return gettext('Bad request')
        elif status == 401:
            return gettext('Unauthorized')
        elif status == 403:
            return gettext('Forbidden')
        else:
            return gettext('Not found')
    elif 500 <= status < 600:
        return gettext('Unable to connect')
    else:
        return gettext(f'Unknown error: {status}')


async def make_request(client, url):
    try:
        response = await client.head(url)
        status_code = response.status_code
        message = get_custom_message(status_code)
    except httpx.InvalidURL as e:
        status_code = getattr(e, 'status_code', 500)
        message = get_custom_message(status_code)
    except httpx.HTTPError as e:
        status_code = getattr(e, 'status_code', 500)
        message = get_custom_message(status_code)

    result = {
        'link': url,
        'status_code': status_code,
        'status_message': message,
    }

    return result


async def check_links(urls):
    headers = {"User-agent": "Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0"}

    async with httpx.AsyncClient(verify=False, headers=headers, follow_redirects=True) as client:
        tasks = [asyncio.ensure_future(make_request(client, url)) for url in urls]
        results = await asyncio.gather(*tasks)

    filtered_results = [result['link'] for result in results if result['status_code'] != 200]

    return filtered_results
