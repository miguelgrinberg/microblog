pipeline {
    agent any
    
    stages {
        stage('Build') {
            steps {
                sh 'docker build -t microblog:latest .'   
            }
        }
        stage('Deploy') {
            steps {
                // Stop running microblog container
                sh 'docker stop $(docker ps -q --filter ancestor=microblog:latest) || true && docker rm $(docker ps -q --filter ancestor=microblog:latest) || true'
                // Prune old containers that are not running
                sh 'docker container prune -f'
                // Deploy new container
                sh 'docker run --name microblog -d -p 5000:5000 --rm microblog:latest'
                // Remove all images that don't have a container running them
                sh 'docker image prune -a'
            }
        }
        stage('Selenium Tests') {
            steps {
                echo 'Running Selenium Tests...'
                //sh 'python3 selenium.py'
            }
        }
    }
    
    // Post always runs even if the pipeline fails
    post {
        success {
            echo 'Pipeline has completed'
             discordSend description: '', footer: '', image: '', link: 'http://3.91.14.163:8080', result: '', scmWebUrl: '', thumbnail: '', title: 
                'Pipeline has completed ✅', webhookURL: 'https://discord.com/api/webhooks/1075879011667955872/Nk0gmKZkrISEs-hru-HjtzzgezWweABCdPsOKGIzkmj5xMcqKC3m1-dx7GZSu0yURAOo'
        }
        failure {
            echo 'Something has failed!'
             discordSend description: 'Pipeline has failed!', footer: '', image: '', link: 'http://3.91.14.163:8080', result: '', scmWebUrl: '', thumbnail: '', title: 
                'Pipeline failure ❌', webhookURL: 'https://discord.com/api/webhooks/1075879011667955872/Nk0gmKZkrISEs-hru-HjtzzgezWweABCdPsOKGIzkmj5xMcqKC3m1-dx7GZSu0yURAOo'
        }
    }
}
