#!/bin/bash
num=$1
sed -i 's/test_mode = [01]/test_mode = '"$num"'/g' {1,2,3}.conf
grep test_mode *.conf
