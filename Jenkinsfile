pipeline {
    agent any

    environment {
        REGISTRY   = "sharath1"
        IMAGE_NAME = "spinnaker-workflow"
        IMAGE_TAG  = "${env.BUILD_NUMBER}"
        FULL_IMAGE = "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build image') {
            steps {
                dir('app') {
                    sh "docker build --build-arg APP_VERSION=${IMAGE_TAG} -t ${FULL_IMAGE} ."
                }
            }
        }

        stage('Push image') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'docker-registry-creds',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh """
                        echo \$DOCKER_PASS | docker login  -u \$DOCKER_USER --password-stdin
                        docker push ${FULL_IMAGE}
                    """
                }
            }
        }

        stage('Tag latest') {
            steps {
                sh """
                    docker tag ${FULL_IMAGE} ${REGISTRY}/${IMAGE_NAME}:latest
                    docker push ${REGISTRY}/${IMAGE_NAME}:latest
                """
            }
        }

        // This is the key stage for Spinnaker integration.
        // Spinnaker's Jenkins trigger can read a ".properties" file archived
        // as a build artifact, and expose each key as ${trigger.properties.KEY}
        // inside the pipeline. This is how we pass the exact image/tag that
        // was just built into the deploy stage, without hardcoding anything.
        stage('Write properties file for Spinnaker') {
            steps {
                sh """
                    cat > image-info.properties <<EOF
DOCKER_IMAGE=${REGISTRY}/${IMAGE_NAME}
DOCKER_TAG=${IMAGE_TAG}
FULL_IMAGE=${FULL_IMAGE}
EOF
                """
                archiveArtifacts artifacts: 'image-info.properties', fingerprint: true
            }
        }
    }

    post {
        always {
            sh "docker logout ${REGISTRY} || true"
        }
        success {
            echo "Built and pushed ${FULL_IMAGE}"
        }
        failure {
            echo "Build failed"
        }
    }
}
