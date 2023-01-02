.PHONY: clean all

JS_SRCS := $(wildcard www/js/*.js)
CSS_SRCS := $(wildcard www/css/*.css)

all: www/app.rel.js www/rel.css build

build:
	mkdir -p build
	npm install --prefix ./build  @babel/core @babel/cli @babel/preset-env @babel/preset-react babel-preset-minify uglifycss --save-dev
	cp ./babel.config.json ./build

clean:
	rm -f www/app.rel.js www/rel.css

www/app.rel.js: $(JS_SRCS)
	cd build && ./node_modules/.bin/babel -o ../$@ --no-comments --compact true --minified $(patsubst %, ../%, $(JS_SRCS))

www/rel.css: $(CSS_SRCS)
	./build/node_modules/.bin/uglifycss --output $@ $(CSS_SRCS)