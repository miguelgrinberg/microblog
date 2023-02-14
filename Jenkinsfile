pipeline {
  agent { dockerfile true } 

  stages {

    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Build') {
      steps {
        sh 'docker build -t microblog:latest .'
      }
    }

  }

}
