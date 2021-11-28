# Builds the binary and copies it to the Docker container.
.DEFAULT_GOAL     := all
SRC_DIR           := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
CLIENT_SRC_DIR    := $(SRC_DIR)/client
SERVER_SRC_DIR    := $(SRC_DIR)/server
BIN_DIR           := $(SRC_DIR)/bin
VERSION           := v0.1
CLOUD_SVC_NAME    := cmu-14-848-search-engine
LOCAL_SVC_NAME    := cmu-14-848-search-client
CLOUD_SVC_PORT    := 80
LOCAL_SVC_PORT    := 8080
CLOUD_REGION      := us-east1
CLOUD_PROJECT     := cmu-14-848
GCR_CLIENT_DOCKER := "gcr.io/cmu-14-848/14-848-search/client:$(VERSION)"
GCR_SERVER_DOCKER := "gcr.io/cmu-14-848/14-848-search/server:$(VERSION)"


# Note(s):
#  - This step needs the `gcloud' binary. After installing,
#    run `gcloud init' to configure access to Google Cloud
#    Platform.
auth:
	# This is required to push images to GCR.
	gcloud auth configure-docker gcr.io

build:
	docker build -t $(GCR_CLIENT_DOCKER) $(CLIENT_SRC_DIR)
	docker build -t $(GCR_SERVER_DOCKER) $(SERVER_SRC_DIR)

push:
	docker push $(GCR_CLIENT_DOCKER)
	docker push $(GCR_SERVER_DOCKER)

deploy: build push
	gcloud run deploy --region $(CLOUD_REGION)  \
	--image $(GCR_SERVER_DOCKER)                \
	--port $(CLOUD_SVC_PORT) $(CLOUD_SVC_NAME)  \
	--allow-unauthenticated

client:
	$(eval SERVER := $(shell basename $(shell gcloud run services describe \
	$(CLOUD_SVC_NAME) --platform managed --region $(CLOUD_REGION) --format \
	'value(status.url)')))
	docker run --name $(LOCAL_SVC_NAME)        \
	-d -p $(LOCAL_SVC_PORT):$(CLOUD_SVC_PORT)  \
	-e "SERVER=$(SERVER)" $(GCR_CLIENT_DOCKER)
	@echo "Client: 'http://localhost:$(LOCAL_SVC_PORT)'."

clean:
	docker stop $(LOCAL_SVC_NAME)
	docker rm $(LOCAL_SVC_NAME)
	docker rmi $(GCR_SERVER_DOCKER)
	docker rmi $(GCR_CLIENT_DOCKER)
	gcloud container images delete $(GCR_CLIENT_DOCKER) --force-delete-tags
	gcloud container images delete $(GCR_SERVER_DOCKER) --force-delete-tags
	gcloud run services delete $(CLOUD_SVC_NAME) --region $(CLOUD_REGION)

all: auth build push deploy client
.PHONY: auth build push deploy client clean
