#!/bin/bash

export AZURE_TESTING=1

pip install -vv git+https://github.com/NSLS-II-ISS/isstools@main
pip install -vv git+https://github.com/NSLS-II-ISS/xas@master
# TODO: fix the branch once the PR https://github.com/NSLS-II-ISS/xview/pull/3 merged.
pip install -vv git+https://github.com/NSLS-II-ISS/xview@add-inits
pip install -vv git+https://github.com/NSLS-II-ISS/isscloudtools@master "oauth2client<4.0.0"


# Create non-standard directories:
sudo mkdir -v -p /nsls2/xf08id/metadata/
sudo mkdir -v -p /mnt/xf08ida-ioc1/
sudo chmod -Rv go+rw /nsls2/xf08id/ /mnt/xf08ida-ioc1/

for f in .ci/test-files/test_[0-9]*; do
    cp -v $f /mnt/xf08ida-ioc1/
done

