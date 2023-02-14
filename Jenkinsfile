pipeline {
  agent any

  stages {
    stage('Build') {
      steps {
        node {
          checkout scm
          def customImage = docker.build("microblog:latest")
        }
      }
    }

  }

}
