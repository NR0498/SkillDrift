FROM solr:9.8

EXPOSE 8983

CMD ["bash", "-lc", "chown -R solr:solr /var/solr && exec gosu solr:solr solr-precreate jobs_core"]
