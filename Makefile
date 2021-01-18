test:
	python3 -m pytest -s

upload:
	python3 setup.py sdist bdist_wheel --universal
	twine upload dist/*
