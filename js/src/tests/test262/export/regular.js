{author: Jeff Walden <jwalden+code@mit.edu>, description: '|await| is excluded from
    LexicalDeclaration by grammar parameter, in AsyncFunction.  Therefore |let| followed
    by |await| inside AsyncFunction is an ASI opportunity, and this code must parse
    without error.', esid: sec-let-and-const-declarations}
