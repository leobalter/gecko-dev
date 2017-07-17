// Copyright (C) 2017 Mozilla Corporation. All rights reserved.
// This code is governed by the BSD license found in the LICENSE file.

/*---
esid: pending
description: reportCompare
---*/

var a = 42;







assert.sameValue(42, foo);
assert.sameValue(foo, bar);
assert.sameValue(call(x), call(y));

// with comment
// with comment
// with comment
// with comment

assert.sameValue(42, foo); // with comment
assert.sameValue(foo, bar); // with comment
assert.sameValue(call(x), call(y)); // with comment

// Blocks:
if (true) {
    // this was a reportCompare Line
    assert.sameValue(foo, 42, "message");
}

// at the EOF, no \n