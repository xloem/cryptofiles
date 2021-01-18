test:
	python3 -m pytest -s

upload: parts
	python3 setup.py sdist bdist_wheel --universal
	twine upload dist/*

parts: cryptofiles/envelope_pb2.py

%_pb2.py: %.proto
	protoc --python_out="$(@D)" --proto_path="$(<D)" "$<"
