author: Jeff Walden <jwalden+code@mit.edu>
description: 'Outside AsyncFunction, |await| is a perfectly cromulent LexicalDeclaration
  variable name.  Therefore ASI doesn''t apply, and so the |0| where a |=| was expected
  is a syntax error.

  '
esid: sec-let-and-const-declarations
negative: {phase: early, type: SyntaxError}
