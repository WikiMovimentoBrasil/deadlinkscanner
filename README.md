# <img src="/static/images/logo.svg" alt="Icon" width="20"/> Dead Link Scanner

## Overview

This Flask application retrieves a list of pages within a specified category of a Wikimedia Project and identifies which external links within each page are dead. It was developed to fulfill a request from the [Lusophone technological wishlist](https://meta.wikimedia.org/wiki/Lista_de_desejos_tecnológicos_da_lusofonia) and was further enhanced during an [Outreachy project](https://www.outreachy.org).

## Features

- Retrieves pages in a specified category from a Wikimedia Project;
- Checks each page for dead external links;
- Displays the results indicating which links are dead for each page.

## Installation

1. Clone the repository:
````
git clone https://github.com/WikiMovimentoBrasil/deadlinkscanner.git
````

2. Set up a virtual environment (optional but recommended):
````
python -m venv venv
source venv/bin/activate # On Windows use venv\Scripts\activate
````

3. Install the dependencies:
````
pip install -r requirements.txt
````

4. Set up a `config.yaml` file with the following configuration:
````
SECRET_KEY: "YOUR_SECRET_KEY"
BABEL_DEFAULT_LOCALE: "DEFAULT_LANGUAGE"
APPLICATION_ROOT: "APPLICATION_ROOT/"
OAUTH_MWURI: "https://meta.wikimedia.org/w/index.php"
CONSUMER_KEY: "YOUR CONSUMER KEY"
CONSUMER_SECRET: "YOUR CONSUMER SECRET"
LANGUAGES: ["pt","en", "<OTHER LANGUAGES>]
````

5. Run the application :
````
flask run
````

6. Navigate to `http://localhost:5000` in your web browser to access the application.

## Usage

1. Enter the url of the page of a Wikimedia project category.
2. Define the depth of subcategories you want to search.
3. Click in 'Submit' and wait for the application to retrieve and process the information.
4. View the results in the CSV file showing which external links are dead for each page.

## Acknowledgments

- This application was inspired by a [request from the Lusophone technological wishlist](https://w.wiki/6vkq).
- Development of this application was partially supported by an Outreachy project.
- Inspiration of the background code was extracted from the work of [Alwoch Sophia](https://github.com/Alwoch) in the [DeadLinkChecker](https://github.com/WikiMovimentoBrasil/deadlinkchecker) project.

## License

This project is licensed under the [MIT License](https://opensource.org/license/mit) - see the LICENSE file for details.