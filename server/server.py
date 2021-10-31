import io
import os
import json
import tarfile
import itertools

import nltk
import magic
import flask
import flask_cors
import whoosh.index
import whoosh.fields
import whoosh.qparser
import whoosh.reading
import whoosh.analysis

def load_conf(app_conf_path):
    '''
    Load configuration variables from `config.json'.
    '''
    with open(app_conf_path, 'r') as config:
        return json.loads(config.read())

def get_mine_type(file, allowed, from_buf=False):
    '''
    Verify if the uploaded file.
    '''
    if (from_buf):
        mime_type = magic.from_buffer(file, mime=True)
    else:
        mime_type = magic.from_file(file, mime=True)

    if mime_type in allowed:
        return mime_type

    return None

def init_index(index_dir):
    '''
    Initialize the search index.
    '''
    nltk.download("stopwords")
    stop_words = set(nltk.corpus.stopwords.words('english'))

    analyzer = whoosh.analysis.FancyAnalyzer(stoplist=stop_words)
    schema = whoosh.fields.Schema(
        path=whoosh.fields.ID(stored=True),
        data=whoosh.fields.TEXT(
            stored=False,
            phrase=False,
            vector=True,
            analyzer=analyzer
        )
    )

    if not os.path.exists(index_dir):
        # Create the directory if it does not exist.
        os.mkdir(index_dir)
        index = whoosh.index.create_in(index_dir, schema)
    else:
        # Open a handle to the index.
        index = whoosh.index.open_dir(index_dir)

    return index

def index_files(file_path, file_mime_type, index):
    if file_mime_type == 'text/plain':
        writer = index.writer()

        # If the uploaded file is a plain-text file,
        # just add it to the index.
        with io.open(file_path, 'r', encoding='ascii', errors='replace') as txt:
            writer.add_document(
                path=os.path.basename(file_path),
                data=txt.read()
            )

        writer.commit()
        return True

    elif file_mime_type == 'application/gzip':
        writer = index.writer()

        # If the uploaded file is a "gzip" file, iterate
        # through all the sub-directories and add each
        # text file to the index.
        tar = tarfile.open(file_path, "r:gz")
        for member in tar.getmembers():
            ex_file = tar.extractfile(member)

            # Ignore file we can't extract.
            if not ex_file:
                continue

            # Read the file contents.
            ex_data = ex_file.read()
            ex_mime = get_mine_type(
                ex_data, app_conf['ingest_types'], from_buf=True
            )

            # If it not a text file, ignore it.
            if (ex_mime != 'text/plain'):
                continue

            writer.add_document(
                path=member.name,
                data=ex_data.decode(encoding='ascii', errors='replace')
            )

        writer.commit()
        return True

    return False

def get_all_docs(index):
    '''
    Get all the documents of an index as a dictionary.
    '''
    return dict(index.searcher().iter_docs())

def search_index_term(term, index):
    '''
    Search the index for a given term.
    '''
    results = {
        'term': term,
        'docs': {
            'count': 0,
            'match': []
        },
        'hits': 0,
    }

    docs = get_all_docs(index)

    try:
        with index.searcher() as searcher:
            results['hits'] = int(searcher.frequency("data", term))
            results['docs']['count'] = int(searcher.doc_frequency(
                "data", term
            ))

            postings = searcher.postings("data", term)
            if postings is None:
                return results

            postings_docs = list(postings.all_ids())

            for doc_id in postings_docs:
                # Because it resets the state, search again.
                postings = searcher.postings("data", term)
                postings.skip_to(doc_id)
                results['docs']['match'].append({
                    'path': docs[doc_id]['path'],
                    'hits': int(postings.weight())
                })
    except whoosh.reading.TermNotFound:
        return results
    except ValueError:
        return results

    return results

def search_index_top(n, index):
    '''
    Return the top "n" terms in the index.
    '''
    results = {
        'top': []
    }

    with index.reader() as reader:
        for hits, term in reader.most_frequent_terms("data", n):
            results['top'].append({
                'term': term.decode('ascii'),
                'hits': int(hits)
            })

    return results

# Initialize the web-server.
app = flask.Flask(__name__)
flask_cors.CORS(app)

# Load application configuration data.
app_conf_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'conf.json'
)
app_conf = load_conf(app_conf_path)

# Initialize the index.
index = init_index(index_dir=app_conf['index_dir'])

@app.route('/upload', methods=['POST'])
def upload():
    up_count = 0
    for file_data in flask.request.files.getlist('file[]'):
        save_path = os.path.join(app_conf['upload_dir'], file_data.filename)
        file_data.save(save_path)

        file_mime_type = get_mine_type(save_path, app_conf['ingest_types'])

        if (file_mime_type is not None):
            index_ok = index_files(save_path, file_mime_type, index)
            if not index_ok:
                return flask.jsonify({
                    'message': 'ERR_INDEX'
                }), 500
            else:
                up_count += 1
        else:
            return flask.jsonify({
                'message': 'ERR_BAD_FILE'
            }), 400

    if (up_count > 0):
        return flask.jsonify({
            'message': 'OK',
        }), 200

    return flask.jsonify({
        'message': 'ERR_FILE_EMPTY'
    }), 400


@app.route('/search', methods=['GET'])
def search():
    term = flask.request.args.get('q')
    if term is None:
        return flask.jsonify({
            'message': 'OK',
            'results': []
        }), 200

    results = search_index_term(term.lower(), index)
    return flask.jsonify({
        'message': 'OK',
        'results': results
    }), 200

@app.route('/top', methods=['GET'])
def top():
    n = flask.request.args.get('n')
    if n is None:
        return flask.jsonify({
            'message': 'OK',
            'results': []
        }), 200

    try:
        n = int(n)
    except ValueError:
        return flask.jsonify({
            'message': 'ERR_NUMERIC',
            'results': []
        }), 400

    results = search_index_top(n, index)
    return flask.jsonify({
        'message': 'OK',
        'results': results
    }), 200

@app.route('/', methods=['GET'])
def ping():
    return flask.jsonify({
        'message': 'PONG'
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=app_conf['debug'], threaded=True)
