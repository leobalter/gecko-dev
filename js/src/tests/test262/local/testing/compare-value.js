// Copyright (C) 2017 Mozilla Corporation. All rights reserved.
// This code is governed by the BSD license found in the LICENSE file.

/*---
esid: pending
description: reportCompare
---*/

var a = 42;

reportCompare(0, 0)
reportCompare(0, 0);
reportCompare(0, 0, "ok");
reportCompare(true, true);
reportCompare(true, true, "ok");

reportCompare(42, foo);
reportCompare(foo, bar);
reportCompare(call(x), call(y));

reportCompare(0, 0); // with comment
reportCompare(0, 0, "ok"); // with comment
reportCompare(true, true); // with comment
reportCompare(true, true, "ok"); // with comment

reportCompare(42, foo); // with comment
reportCompare(foo, bar); // with comment
reportCompare(call(x), call(y)); // with comment

// Blocks:
if (true) {
    reportCompare(0, 0); // this was a reportCompare Line
    reportCompare(foo, 42, "message");
}

reportCompare(0, 0); // at the EOF, no \n