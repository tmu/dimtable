--  mysql --user=root -p < create_db.sql
create database dimtable_example;
grant all privileges on dimtable_example.* to 'example'@'localhost' identified by 'example';
