class DocClassifierError(Exception):
    pass

class UnsupportedFormatError(DocClassifierError):
    pass

class ExtractionError(DocClassifierError):
    pass

class FileAccessError(DocClassifierError):
    pass
