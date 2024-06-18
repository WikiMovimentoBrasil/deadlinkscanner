import os
import yaml
import httpx
import mwoauth
import time
import asyncio
import pandas as pd
import tempfile
from flask import Flask, jsonify, request, render_template, send_file, redirect, url_for, session, flash
from flask_babel import Babel
from link_checker import get_pages_in_category, get_external_links_batch, make_request, get_category_project_and_category_name

__dir__ = os.path.dirname(__file__)
app = Flask(__name__)
app.config.update(yaml.safe_load(open(os.path.join(__dir__, 'config.yaml'))))

BABEL = Babel(app)


def get_locale(lang=None):
    if not lang:
        lang = session.get('language', None)

        return lang if not lang else request.accept_languages.best_match(app.config["LANGUAGES"])


@app.route('/set_locale')
def set_locale():
    lang = request.args.get('language', None)
    if not lang:
        lang = request.accept_languages.best_match(app.config["LANGUAGES"])

    session["language"] = lang
    return redirect(url_for('index'))


BABEL.init_app(app, locale_selector=get_locale)


@app.route('/login')
def login():
    consumer_token = mwoauth.ConsumerToken(app.config['CONSUMER_KEY'], app.config['CONSUMER_SECRET'])
    try:
        redirect_, request_token = mwoauth.initiate(app.config['OAUTH_MWURI'], consumer_token)
    except Exception:
        app.logger.exception('mwoauth.initiate failed')
        return redirect(url_for('index'))
    else:
        session['request_token'] = dict(zip(request_token._fields, request_token))
        return redirect(redirect_)


@app.route('/oauth-callback', methods=["GET"])
def oauth_callback():
    if 'request_token' not in session:
        flash(u'OAuth callback failed. Are cookies disabled?', 'danger')
        return redirect(url_for('index'))

    consumer_token = mwoauth.ConsumerToken(app.config['CONSUMER_KEY'], app.config['CONSUMER_SECRET'])

    try:
        access_token = mwoauth.complete(
            app.config['OAUTH_MWURI'],
            consumer_token,
            mwoauth.RequestToken(**session['request_token']),
            request.query_string)
        identity = mwoauth.identify(app.config['OAUTH_MWURI'], consumer_token, access_token)
        print(identity)
    except Exception:
        app.logger.exception('OAuth authentication failed')
    else:
        session['access_token'] = dict(zip(access_token._fields, access_token))
        session['username'] = identity['username']
        flash(
            "You were signed in, %s!" % identity["username"], "success"
        )

    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/', methods=('GET', 'POST'))
def index():
    username = session.get('username', None)
    if request.method == 'POST':
        data = request.form['category_url']
        return render_template('home.html', message=f'Form submitted with: {data}', username=username)
    return render_template('home.html', title='Home', username=username)


@app.route('/submit', methods=['POST'])
def submit():
    category_url = request.form.get('category_url')
    depth = request.form.get('depth', type=int, default=0)
    project, category_page = get_category_project_and_category_name(category_url)
    category_name = category_page.split(':', 1)[1]

    task, task_status_code = asyncio.run(check_links(category_url, True, depth))

    pages = []
    links = []
    status_codes = []
    status_messages = []

    for page, page_links in task.items():
        for detail in page_links:
            pages.append(page)
            links.append(detail['link'])
            status_codes.append(detail['status_code'])
            status_messages.append(detail['status_message'])

    df = pd.DataFrame({
        'File': pages,
        'Link': links,
        'Status Code': status_codes,
        'Status Message': status_messages
    })

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    df.to_csv(temp_file.name, index=False)
    response = send_file(temp_file.name, as_attachment=True, download_name=f'{category_name}.csv')
    temp_file.close()

    return response


def get_url_parameters(args):
    category_url = args.get('category_url')
    get_subcategories = args.get('get_subcategories', type=bool, default=False)
    depth = args.get('depth', type=int, default=0)

    return category_url, get_subcategories, depth


async def category_pages(category_url, get_subcategories, depth):
    pages = await get_pages_in_category(category_url, get_subcategories, depth, 0)
    cleaned_pages = list(set([page['title'] for page in pages if page['ns'] != 14]))

    return cleaned_pages, 200


@app.route('/category_pages', methods=['GET'])
def trigger_category_pages():
    category_url, get_subcategories, depth = get_url_parameters(request.args)
    if not category_url:
        return jsonify({'error': 'Category URL parameter is required'}), 400

    task, task_status_code = asyncio.run(category_pages(category_url, get_subcategories, depth))

    return task


async def external_links(category_url, get_subcategories, depth):
    page_titles, page_titles_status_code = await category_pages(category_url, get_subcategories, depth)
    if not page_titles:
        return {}, 400
    try:
        results = await get_external_links_batch(category_url, page_titles)
        response_data = {title: links for title, links in results}
        return response_data, 200
    except Exception as e:
        return {}, 400


@app.route('/external_links', methods=['GET'])
def trigger_external_links():
    category_url, get_subcategories, depth = get_url_parameters(request.args)
    if not category_url:
        return jsonify({'error': 'Category URL parameter is required'}), 400

    task, task_status_code = asyncio.run(external_links(category_url, get_subcategories, depth))

    return task


async def check_links(category_url, get_subcategories, depth):
    start_time = time.time()
    urls, urls_status_code = await external_links(category_url, get_subcategories, depth)
    headers = {'User-agent': 'Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0'}

    async with httpx.AsyncClient(verify=False, headers=headers, follow_redirects=True) as client:
        response_data = {}
        for page_title, page_links in urls.items():
            broken_links = []
            tasks = [asyncio.ensure_future(make_request(client, url)) for url in page_links]
            results = await asyncio.gather(*tasks)

            page_broken_links = [result for result in results if result['status_code'] != 200]
            broken_links.extend(page_broken_links)
            if broken_links:
                response_data[page_title] = broken_links

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f'Total elapsed time: {elapsed_time:.2f} seconds')
    return response_data, 200


@app.route('/check_links', methods=['GET'])
def trigger_check_links():
    category_url, get_subcategories, depth = get_url_parameters(request.args)
    if not category_url:
        return jsonify({'error': 'Category URL parameter is required'}), 400

    task, task_status_code = asyncio.run(check_links(category_url, get_subcategories, depth))

    return task


if __name__ == '__main__':
    app.run(port=8000)
