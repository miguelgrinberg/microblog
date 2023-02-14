pipeline {
  agent any

  stages {
    stage('Build') {
      steps {
        sh 'echo building...'
        sh 'docker run -p 5000:5000 microblog:latest'
      }
    }

  }

}
