import subprocess


"""Provide utilities to read/write/download dataset. Most of the dataset is stored in Github, except for large dataset we store them 

Each dataset is stored in a folder with the following structures:

<dataset_name>
    <version>
        . metadata.json: { version, url, date }
        . tables:
            <table_id>.csv - we use csv over json as it's easier to preview - all tables are relational tables with first row as header.
        . wikidata:
            . entities:
                <table_id>.csv
            . descriptions:
                <table_id>/<version.xx.json>
"""
def read_dataset():
    pass


def download():
    """Download and unpack the dataset"""
    pass


def upload():
    """Upload the dataset to a remote server"""
    pass
