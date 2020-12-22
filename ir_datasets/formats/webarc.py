import gzip
import re
from contextlib import contextmanager, ExitStack
from typing import NamedTuple
import ir_datasets
from ir_datasets.formats import BaseDocs


class WarcDoc(NamedTuple):
    doc_id: str
    url: str
    date: str
    http_headers: bytes
    body: bytes
    body_content_type: str


class WarcDocs(BaseDocs):
    def __init__(self, id_header='WARC-TREC-ID', warc_cw09=False):
        super().__init__()
        self.id_header = id_header
        self.warc_cw09 = warc_cw09

    def docs_iter(self):
        for source_file in self._docs_iter_source_files():
            with self._docs_ctxt_iter_warc(source_file) as doc_iter:
                yield from doc_iter

    @contextmanager
    def _docs_ctxt_iter_warc(self, warcf):
        if self.warc_cw09:
            warc = ir_datasets.lazy_libs.warc_clueweb09()
        else:
            warc = ir_datasets.lazy_libs.warc()

        with ExitStack() as stack:
            if isinstance(warcf, str):
                warcf = stack.enter_context(gzip.open(warcf, 'rb'))
            f = stack.enter_context(warc.WARCFile(fileobj=warcf))
            def it():
                for doc in filter(lambda d: d.type == 'response', f):
                    did = doc[self.id_header]
                    url = doc['WARC-Target-URI']
                    date = doc['WARC-Date']
                    payload = doc.payload.read()
                    split = re.split(b'\r?\n\r?\n', payload, maxsplit=1)
                    if len(split) == 1:
                        http_headers, body = split[0], b''
                    else:
                        http_headers, body = split
                    content_type = re.search(b'Content-Type:(.*)', http_headers, flags=re.IGNORECASE)
                    if content_type:
                        content_type = content_type.group(1).decode().strip()
                        content_type = content_type.split(';')
                        content_type = content_type[0]
                    else:
                        content_type = ''
                    yield WarcDoc(did, url, date, http_headers, body, content_type)
            yield it()

    def docs_path(self):
        raise NotImplementedError

    def _docs_iter_source_files(self):
        raise NotImplementedError

    def _docs_id_to_source_file(self, doc_id):
        # For Warc Docstore lookups
        raise NotImplementedError

    def _docs_source_file_to_checkpoint(self, source_file):
        # For Warc Docstore lookups
        return None

    def docs_store(self):
        docstore = ir_datasets.indices.ClueWebWarcDocstore(self)
        return ir_datasets.indices.CacheDocstore(docstore, f'{self.docs_path()}.cache')

    def docs_cls(self):
        return WarcDoc
